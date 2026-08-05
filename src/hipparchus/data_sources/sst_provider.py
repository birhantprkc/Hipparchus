"""Sea surface temperature, drawn the way this application draws every other
scalar field.

The point of this file is how little is in it. The contour tracer, the
shapely-backed banding and the two-stop ramp were written for elevation and
know nothing about degrees Celsius -- so a temperature is the same pipeline
pointed at a different array. What was missing was a way to *get* the array,
and that is :mod:`hipparchus.data_sources.erddap`, already built for the
currents.

Adding the next ocean scalar is an ``ERDDAPDataset`` and two style entries --
the promise the brief made about ERDDAP, kept here for the product it was
made for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from shapely.geometry import mapping

from hipparchus.data_sources.erddap import (
    ERDDAPClient,
    ERDDAPDataset,
    ERDDAPError,
    ERDDAPNotAGrid,
    HttpGet,
)
from hipparchus.data_sources.map_models import ProviderStatus
from hipparchus.data_sources.provider import BBoxQuery, FeatureCollection, GeoJSONMapping
from hipparchus.data_sources.simulated_field import nice_interval
from hipparchus.geometry.bands import band_boundaries, elevation_bands, map_coordinates
from hipparchus.geometry.contours import contour_levels, contour_polylines, polyline_to_lonlat

SST_PROVIDER_ID = "erddap_sst"
SST_PROVIDER_LABEL = "Sea surface temperature"
SST_CONTOURS_LAYER = "sst_contours"
SST_BANDS_LAYER = "sst_bands"

#: NASA JPL's Multi-scale Ultra-high Resolution analysis, a daily global 0.01°
#: grid -- the finest routinely updated sea surface temperature ERDDAP serves.
DEFAULT_DATASET = ERDDAPDataset(
    server="https://coastwatch.pfeg.noaa.gov/erddap",
    dataset_id="jplMURSST41",
    variable="analysed_sst",
    layer_prefix="sst",
    unit="°C",
    nominal_resolution=0.01,
)


@dataclass(slots=True)
class SstSettings:
    dataset: ERDDAPDataset = DEFAULT_DATASET
    #: Filled bands under the isolines, the way elevation gets both.
    band_count: int = 8
    #: Isolines. Zero picks a round interval from the range actually in view --
    #: the same rule the elevation contour interval follows: a fixed step
    #: empties a small frame and floods a large one.
    contour_interval: float = 0.0
    target_line_count: int = 14
    target_samples: int = 220
    timeout_seconds: float = 45.0
    #: Bands are broad, so they are traced on a decimated copy -- full
    #: resolution costs paths and shows nothing a fill can carry.
    band_grid_max_pixels: int = 260


@dataclass(slots=True)
class SstProvider:
    """Fetches an ocean scalar field and draws it as filled bands and isolines."""

    settings: SstSettings = field(default_factory=SstSettings)
    http_get: HttpGet | None = None
    provider_id: str = SST_PROVIDER_ID
    label: str = SST_PROVIDER_LABEL
    # Accepted so every optional provider can be configured alike; unused.
    source_path: Path | None = None

    def status(self) -> ProviderStatus:
        """What the sources panel shows before anything is fetched.

        Every provider has one, and the manager asks all of them -- so a
        provider without it takes down the panel for the others rather than
        merely being absent itself.
        """
        return ProviderStatus(
            provider_id=self.provider_id,
            label=self.label,
            available=True,
            detail=(
                f"{self.settings.dataset.dataset_id} · "
                f"{self.settings.dataset.nominal_resolution:g}° sea surface temperature"
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
        grid = client.grid(bbox)

        rows, columns = grid.values.shape
        if rows < 2 or columns < 2:
            raise ERDDAPError("the sea surface temperature field came back smaller than two cells")

        finite = grid.values[np.isfinite(grid.values)]
        if finite.size == 0 or float(finite.max()) <= float(finite.min()):
            raise ERDDAPNotAGrid("every sample is the same value or missing")
        minimum, maximum = float(finite.min()), float(finite.max())

        interval = self.settings.contour_interval
        if interval <= 0:
            interval = nice_interval(maximum - minimum, target_lines=self.settings.target_line_count)

        contour_features = self._contour_features(grid.values, grid.bounds, grid.unit, interval, minimum, maximum)
        band_features = self._band_features(grid.values, grid.bounds, grid.unit)

        return FeatureCollection(
            features_by_layer={
                SST_CONTOURS_LAYER: contour_features,
                SST_BANDS_LAYER: band_features,
            },
            geojson_by_layer={
                SST_CONTOURS_LAYER: {"type": "FeatureCollection", "features": contour_features},
                SST_BANDS_LAYER: {"type": "FeatureCollection", "features": band_features},
            },
            metadata={
                "source": self.provider_id,
                # A satellite analysis is a measurement -- an interpolated one,
                # which is what "analysed" means in the variable's own name.
                "provenance": "measured",
                "measured": True,
                "erddap_server": self.settings.dataset.server,
                "erddap_dataset": self.settings.dataset.dataset_id,
                "erddap_variable": self.settings.dataset.variable,
                # `[(last)]` is a moving target; a sheet that does not record
                # which step it drew cannot be reproduced from its own
                # diagnostics.
                "erddap_time": grid.time,
                "value_unit": grid.unit,
                "value_min": minimum,
                "value_max": maximum,
                "contour_interval": interval,
                "grid_rows": rows,
                "grid_columns": columns,
            },
            bbox=bbox,
        )

    def _contour_features(
        self,
        values: np.ndarray,
        bounds: tuple[float, float, float, float],
        unit: str,
        interval: float,
        minimum: float,
        maximum: float,
    ) -> list[GeoJSONMapping]:
        # No index/minor split: a densely contoured sheet reads its value from
        # line density, and a heavier line every fifth only interrupts that.
        levels = contour_levels(minimum, maximum, interval=interval, index_every=0)
        features: list[GeoJSONMapping] = []
        for level in levels.all_levels:
            for polyline in contour_polylines(values, level):
                coordinates = polyline_to_lonlat(polyline, bounds=bounds, shape=values.shape)
                if len(coordinates) < 2:
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "id": f"{self.provider_id}/{SST_CONTOURS_LAYER}/{level:.3f}/{len(features)}",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [list(pair) for pair in coordinates],
                        },
                        "properties": {
                            "hipparchus_layer": SST_CONTOURS_LAYER,
                            "hipparchus_source": self.provider_id,
                            "value": level,
                            "unit": unit,
                            "contour_interval": interval,
                        },
                    }
                )
        return features

    def _band_features(
        self, values: np.ndarray, bounds: tuple[float, float, float, float], unit: str
    ) -> list[GeoJSONMapping]:
        if self.settings.band_count < 2:
            return []
        step = max(
            1, int(math.ceil(max(values.shape) / max(16, self.settings.band_grid_max_pixels)))
        )
        coarse = values[::step, ::step]
        finite = coarse[np.isfinite(coarse)]
        if finite.size == 0:
            return []
        coarse_min, coarse_max = float(finite.min()), float(finite.max())
        if coarse_max <= coarse_min:
            return []

        boundaries = band_boundaries(coarse_min, coarse_max, self.settings.band_count)
        bands = elevation_bands(coarse, boundaries)
        if not bands:
            return []

        # A plain lon/lat lattice, so index space maps to the world by linear
        # interpolation over the *coarse* grid's own dimensions -- decimation
        # changes the index scale, not the geography the bounds still span.
        min_lon, min_lat, max_lon, max_lat = bounds
        coarse_rows, coarse_columns = coarse.shape
        col_span = (max_lon - min_lon) / max(1, coarse_columns - 1)
        row_span = (max_lat - min_lat) / max(1, coarse_rows - 1)

        def to_lonlat(row: float, col: float) -> tuple[float, float]:
            return (min_lon + col * col_span, max_lat - row * row_span)

        features: list[GeoJSONMapping] = []
        for index, band in enumerate(bands):
            geometry = map_coordinates(band.geometry, to_lonlat)
            if geometry.is_empty:
                continue
            features.append(
                {
                    "type": "Feature",
                    "id": f"{self.provider_id}/{SST_BANDS_LAYER}/{index}",
                    "geometry": mapping(geometry),
                    "properties": {
                        "hipparchus_layer": SST_BANDS_LAYER,
                        "hipparchus_source": self.provider_id,
                        "value_low": band.lower,
                        "value_high": band.upper,
                        "unit": unit,
                        "band_index": index,
                        "band_count": len(bands),
                    },
                }
            )
        return features
