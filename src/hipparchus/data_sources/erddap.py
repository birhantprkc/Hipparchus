"""One client for a federated network of ocean data.

ERDDAP is a REST protocol with server-side subsetting, and hundreds of servers
speak it — NOAA CoastWatch, IOOS, IFREMER, academic institutions. Sea surface
temperature, salinity, wave height, ocean colour, surface winds, buoy
observations: **one client reaches all of it**, and each product arrives as a
grid this application already knows how to contour, band and shade.

**CSV, not NetCDF and not GeoTIFF**, all three of which griddap offers. NetCDF
would want an HDF5 reader; GeoTIFF a raster one. The CSV carries its own units in
the second header row, and a format that states what its numbers mean is worth
more here than one that saves bytes.

Two things the parsing does not take on trust. **The grid is rebuilt from the
coordinates that arrived** rather than from the ones that were asked for, because
a server may snap a range to its own cell edges and a grid laid out by the
request is a map of somewhere slightly else. And **row 0 is made north** whatever
order the rows came in — griddap sends south first, and a smooth field upside
down looks perfectly fine.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from typing import Callable
from urllib.request import Request, urlopen

import numpy as np

HttpGet = Callable[[str, float], bytes]


class ERDDAPError(RuntimeError):
    """The server said no, or said something this cannot read."""


class ERDDAPRefused(ERDDAPError):
    """A plain-text ``Error { … }`` document rather than data."""


class ERDDAPNotAGrid(ERDDAPError):
    """A body that parsed but is not a grid of the variable asked for."""


@dataclass(frozen=True, slots=True)
class ERDDAPDataset:
    """Which server, which dataset, which variable — and what to call the layers."""

    server: str
    dataset_id: str
    variable: str
    layer_prefix: str
    unit: str
    nominal_resolution: float


@dataclass(slots=True)
class ERDDAPGrid:
    """A field as it came back, with the bounds it actually covers."""

    values: np.ndarray
    #: ``(min_lon, min_lat, max_lon, max_lat)`` read off the coordinates.
    bounds: tuple[float, float, float, float]
    unit: str
    time: str


@dataclass(slots=True)
class ERDDAPClient:
    dataset: ERDDAPDataset
    #: Roughly how many samples across the frame. Server-side striding is the
    #: thing ERDDAP is good at, and it is how a frame the size of the Aegean does
    #: not come back as a million rows of text.
    target_samples: int = 160
    timeout_seconds: float = 45.0
    http_get: HttpGet | None = None

    def stride(self, bbox: tuple[float, float, float, float]) -> int:
        min_lon, min_lat, max_lon, max_lat = bbox
        span = max(abs(max_lon - min_lon), abs(max_lat - min_lat))
        cells = span / max(1e-9, self.dataset.nominal_resolution)
        return max(1, int(cells / max(1, self.target_samples)))

    def _selection(self, bbox: tuple[float, float, float, float]) -> str:
        min_lon, min_lat, max_lon, max_lat = bbox
        step = self.stride(bbox)
        return (
            "[(last)]"
            f"[({min_lat}):{step}:({max_lat})]"
            f"[({min_lon}):{step}:({max_lon})]"
        )

    def url(self, bbox: tuple[float, float, float, float]) -> str:
        query = f"{self.dataset.variable}{self._selection(bbox)}"
        return f"{self.dataset.server}/griddap/{self.dataset.dataset_id}.csv?{query}"

    def vector_url(self, bbox: tuple[float, float, float, float], second: str) -> str:
        """Two variables in one request, for a vector field.

        griddap takes a comma-separated list, each with its own dimension
        selection, and answers with one CSV carrying both columns — so a current
        costs one round trip rather than two, and **the two components are
        guaranteed to be the same time step and the same lattice.** Fetched
        separately they might not be.
        """
        selection = self._selection(bbox)
        query = f"{self.dataset.variable}{selection},{second}{selection}"
        return f"{self.dataset.server}/griddap/{self.dataset.dataset_id}.csv?{query}"

    def vector_grid(
        self, bbox: tuple[float, float, float, float], second: str
    ) -> tuple[ERDDAPGrid, ERDDAPGrid]:
        """The eastward and northward halves of a flow, on one lattice."""
        text = self._fetch(self.vector_url(bbox, second))
        return parse(text, self.dataset.variable), parse(text, second)

    def grid(self, bbox: tuple[float, float, float, float]) -> ERDDAPGrid:
        return parse(self._fetch(self.url(bbox)), self.dataset.variable)

    def _fetch(self, url: str) -> str:
        getter = self.http_get or _default_http_get
        try:
            body = getter(url, self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as provider status
            raise ERDDAPError(f"ERDDAP request failed: {exc}") from exc
        return body.decode("utf-8", errors="replace")


def _default_http_get(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, method="GET")
    request.add_header("User-Agent", "Hipparchus (open-source map generator)")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read()


def parse(text: str, variable: str) -> ERDDAPGrid:
    """griddap's CSV: a row of column names, a row of units, then the data."""
    stripped = text.lstrip()
    # ERDDAP reports failure as a plain-text `Error { … }` document, so the shape
    # of the body decides rather than a status code.
    if stripped.startswith("Error") or stripped.startswith("<"):
        raise ERDDAPRefused(stripped.splitlines()[0][:200] if stripped else "empty response")

    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        raise ERDDAPNotAGrid("too few rows to be a grid")

    header = [name.strip() for name in rows[0]]
    units = [unit.strip() for unit in rows[1]]
    for needed in ("latitude", "longitude", variable):
        if needed not in header:
            raise ERDDAPNotAGrid(f"the response has no {needed!r} column")

    lat_at = header.index("latitude")
    lon_at = header.index("longitude")
    value_at = header.index(variable)
    time_at = header.index("time") if "time" in header else None

    samples: dict[tuple[float, float], float] = {}
    latitudes: set[float] = set()
    longitudes: set[float] = set()
    time = ""
    for row in rows[2:]:
        if len(row) <= max(lat_at, lon_at, value_at):
            continue
        try:
            lat = float(row[lat_at])
            lon = float(row[lon_at])
        except ValueError:
            continue
        raw = row[value_at].strip()
        # A missing sample has to stay missing: the tracer reads NaN as "nothing
        # here", and a zero would be a real and very slack current.
        try:
            value = float(raw) if raw and raw.upper() != "NAN" else math.nan
        except ValueError:
            value = math.nan
        samples[(lat, lon)] = value
        latitudes.add(lat)
        longitudes.add(lon)
        if time_at is not None and not time and len(row) > time_at:
            time = row[time_at].strip()

    if len(latitudes) < 2 or len(longitudes) < 2:
        raise ERDDAPNotAGrid("the response is not two-dimensional")

    # Row 0 is north, as everywhere else here.
    ordered_lat = sorted(latitudes, reverse=True)
    ordered_lon = sorted(longitudes)
    values = np.full((len(ordered_lat), len(ordered_lon)), math.nan, dtype=float)
    for row_index, lat in enumerate(ordered_lat):
        for column_index, lon in enumerate(ordered_lon):
            found = samples.get((lat, lon))
            if found is not None:
                values[row_index, column_index] = found

    return ERDDAPGrid(
        values=values,
        bounds=(ordered_lon[0], ordered_lat[-1], ordered_lon[-1], ordered_lat[0]),
        unit=units[value_at] if value_at < len(units) else "",
        time=time,
    )
