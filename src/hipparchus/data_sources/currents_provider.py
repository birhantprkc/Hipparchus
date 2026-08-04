"""Surface currents, drawn as streamlines rather than animated as particles.

The brief that asked for this assumed CMEMS and a prepared file. **That was
reasoning rather than checking**: NOAA publishes global geostrophic velocities
through the same ERDDAP a sea surface temperature would come from, as ``ugos``
and ``vgos`` on a 0.25° lattice, and both components arrive in one CSV. So a
current costs one round trip and no new network path at all.

What it does need is an integrator, and that is
:mod:`hipparchus.geometry.streamlines`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from hipparchus.data_sources.erddap import (
    ERDDAPClient,
    ERDDAPDataset,
    ERDDAPError,
    HttpGet,
)
from hipparchus.data_sources.map_models import ProviderStatus
from hipparchus.data_sources.provider import BBoxQuery, FeatureCollection, GeoJSONMapping
from hipparchus.geometry.streamlines import (
    StreamlinePoint,
    StreamlineSettings,
    streamlines,
)

CURRENTS_PROVIDER_ID = "erddap_current"
CURRENTS_PROVIDER_LABEL = "Surface currents"
CURRENTS_LAYER = "current_streamlines"

#: NOAA/NESDIS sea surface height, from which the geostrophic velocities are
#: derived. Both components live in the one dataset.
DEFAULT_DATASET = ERDDAPDataset(
    server="https://coastwatch.pfeg.noaa.gov/erddap",
    dataset_id="nesdisSSH1day",
    variable="ugos",
    layer_prefix="current",
    unit="m s-1",
    nominal_resolution=0.25,
)


@dataclass(slots=True)
class CurrentsSettings:
    dataset: ERDDAPDataset = DEFAULT_DATASET
    #: The northward half. The eastward half is the dataset's own ``variable``.
    northward_variable: str = "vgos"
    streamlines: StreamlineSettings = field(default_factory=StreamlineSettings)
    target_samples: int = 160
    timeout_seconds: float = 45.0
    #: Weight bands along a line. A streamline drawn at one width says where the
    #: water goes; one that thickens where the water runs says how fast, which is
    #: the other half of what a current chart is for.
    speed_bands: int = 5
    #: The thinnest and thickest a streamline gets, as multiples of the layer's
    #: own stroke.
    min_stroke_scale: float = 0.45
    max_stroke_scale: float = 2.2


@dataclass(frozen=True, slots=True)
class Run:
    """One stretch of a streamline whose speed sits in a single band."""

    points: tuple[StreamlinePoint, ...]
    speed: float
    #: Where this run sits between the slowest and fastest water on the sheet.
    fraction: float


def runs_of(
    line: Sequence[StreamlinePoint], *, bands: int, slowest: float, fastest: float
) -> list[Run]:
    """Split a streamline where its speed crosses a band edge.

    One feature per run, because a stroke width belongs to a feature. Runs
    overlap by one vertex so the line has no gaps at the joins.
    """
    if len(line) < 2 or bands < 1:
        return []
    span = fastest - slowest

    def band_of(speed: float) -> int:
        if span <= 0:
            return 0
        position = (speed - slowest) / span
        return min(bands - 1, max(0, int(position * bands)))

    def make(points: list[StreamlinePoint], band: int) -> Run:
        speeds = [point.speed for point in points]
        mean = sum(speeds) / max(1, len(speeds))
        fraction = band / (bands - 1) if bands > 1 else 0.0
        return Run(points=tuple(points), speed=mean, fraction=fraction)

    out: list[Run] = []
    current = [line[0]]
    current_band = band_of(line[0].speed)
    for point in line[1:]:
        next_band = band_of(point.speed)
        if next_band == current_band:
            current.append(point)
            continue
        # Overlap by one, so the runs meet rather than leaving a hairline of
        # paper between them.
        current.append(point)
        out.append(make(current, current_band))
        current = [point]
        current_band = next_band
    if len(current) >= 2:
        out.append(make(current, current_band))
    return out


@dataclass(slots=True)
class CurrentsProvider:
    """Fetches geostrophic surface currents and draws them as streamlines."""

    settings: CurrentsSettings = field(default_factory=CurrentsSettings)
    http_get: HttpGet | None = None
    provider_id: str = CURRENTS_PROVIDER_ID
    label: str = CURRENTS_PROVIDER_LABEL
    # Accepted so every optional provider can be configured alike; unused.
    source_path: Path | None = None

    def status(self) -> ProviderStatus:
        """What the sources panel shows before anything is fetched.

        Every provider has one, and the manager asks all of them — so a provider
        without it takes down the panel for the others rather than merely being
        absent itself.
        """
        return ProviderStatus(
            provider_id=self.provider_id,
            label=self.label,
            available=True,
            detail=(
                f"{self.settings.dataset.dataset_id} · "
                f"{self.settings.dataset.nominal_resolution:g}° geostrophic velocities"
            ),
        )

    def fetch_bbox(self, query: BBoxQuery) -> FeatureCollection:
        bbox = (query.min_lon, query.min_lat, query.max_lon, query.max_lat)
        client = ERDDAPClient(
            dataset=self.settings.dataset,
            target_samples=self.settings.target_samples,
            timeout_seconds=self.settings.timeout_seconds,
            http_get=self.http_get,
        )
        east, north = client.vector_grid(bbox, self.settings.northward_variable)

        rows, columns = east.values.shape
        if rows < 2 or columns < 2:
            raise ERDDAPError("the current field came back smaller than two cells")

        min_lon, min_lat, max_lon, max_lat = east.bounds
        cell_lat = (max_lat - min_lat) / (rows - 1)
        cell_lon = (max_lon - min_lon) / (columns - 1)

        lines = streamlines(
            east.values,
            north.values,
            cell_lon_degrees=cell_lon,
            cell_lat_degrees=cell_lat,
            latitude_for_row=lambda row: max_lat - row * cell_lat,
            settings=self.settings.streamlines,
        )

        speeds = [
            point.speed for line in lines for point in line if math.isfinite(point.speed)
        ]
        fastest = max(speeds) if speeds else 0.0
        slowest = min(speeds) if speeds else 0.0

        features: list[GeoJSONMapping] = []
        for index, line in enumerate(lines):
            for run in runs_of(
                line, bands=self.settings.speed_bands, slowest=slowest, fastest=fastest
            ):
                coordinates = [
                    (min_lon + point.column * cell_lon, max_lat - point.row * cell_lat)
                    for point in run.points
                ]
                if len(coordinates) < 2:
                    continue
                scale = self.settings.min_stroke_scale + (
                    self.settings.max_stroke_scale - self.settings.min_stroke_scale
                ) * run.fraction
                features.append(
                    {
                        "type": "Feature",
                        "id": f"{self.provider_id}/{index}/{len(features)}",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [list(pair) for pair in coordinates],
                        },
                        "properties": {
                            "hipparchus_layer": CURRENTS_LAYER,
                            "speed": run.speed,
                            "unit": east.unit,
                            # Read as a multiplier on the layer's stroke, which
                            # is how a streamline thickens where the water runs.
                            "stroke_scale": scale,
                        },
                    }
                )

        return FeatureCollection(
            features_by_layer={CURRENTS_LAYER: features},
            geojson_by_layer={
                CURRENTS_LAYER: {"type": "FeatureCollection", "features": features}
            },
            metadata={
                "source": self.provider_id,
                # Geostrophic velocity is derived from measured sea surface
                # height rather than measured directly, and calling it
                # `measured` would launder a model into an observation.
                "provenance": "approximate",
                "erddap_dataset": self.settings.dataset.dataset_id,
                "erddap_time": east.time,
                "current_unit": east.unit,
                "current_max": fastest,
                "streamline_count": len(lines),
                "grid_rows": rows,
                "grid_columns": columns,
            },
            bbox=bbox,
        )
