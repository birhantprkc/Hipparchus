"""Real elevation for any area on Earth, from public terrain tiles.

Measured ground, not a generated field: AWS's `elevation-tiles-prod` mosaic
(SRTM, NED, GMTED and friends) served as terrarium-encoded PNG over plain HTTPS
with no key and no account. Tiles for the area are fetched, stitched, cropped
and contoured through the same pipeline the rest of the app uses, so a real
mountain arrives as editable vector linework.

Terrarium packs elevation into colour: ``metres = R * 256 + G + B / 256 -
32768``, which covers the whole range from ocean floor to summit at 1/256 m.

Tiles are Web Mercator, so the grid rows are *not* evenly spaced in latitude --
they are evenly spaced in mercator y. Converting a contour vertex back to
lat/lon has to invert that projection rather than interpolate linearly, or every
contour lands slightly north of where it belongs, increasingly so towards the
poles.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import math
from pathlib import Path
import time
from typing import Any, Callable

import numpy as np

from hipparchus.core.fetch_progress import FetchCancelled
from hipparchus.data_sources.map_models import ProviderStatus
from hipparchus.data_sources.optional_providers import _collection_from_layers, _empty_layers
from hipparchus.data_sources.provider import BBoxQuery, FeatureCollection
from shapely.geometry import mapping

from hipparchus.geometry.bands import band_boundaries, elevation_bands, map_coordinates
from hipparchus.geometry.contours import contour_levels, contour_polylines, orient_uphill_left
from hipparchus.geometry.hillshade import SunPosition, hillshade
from hipparchus.geometry.projection import EARTH_RADIUS_M, MAX_MERCATOR_LAT
from hipparchus.data_sources.simulated_field import nice_interval


TERRAIN_TILES_PROVIDER_ID = "terrain_tiles"
TERRAIN_TILES_PROVIDER_LABEL = "Terrain Tiles (real elevation)"
DEFAULT_TERRAIN_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

MINOR_CONTOUR_LAYER = "terrain_contours"
INDEX_CONTOUR_LAYER = "terrain_index_contours"
# Terrarium carries bathymetry in the same band as land, so the sea floor comes
# free with the coast -- but it is a different thing and reads as a different
# thing, so it gets its own layer rather than being drawn as if it were land.
BATHYMETRY_LAYER = "bathymetry"
SUMMIT_LAYER = "summits"
ELEVATION_BANDS_LAYER = "elevation_bands"
HILLSHADE_LAYER = "terrain_hillshade"

TILE_PIXELS = 256
# The mosaic's own limit; asking beyond it returns nothing useful.
MAX_SOURCE_ZOOM = 15

HttpGetBytes = Callable[[str, float], bytes]


class TerrainTileError(RuntimeError):
    """Raised when elevation tiles cannot be fetched or decoded."""


@dataclass(slots=True, frozen=True)
class TerrainTileSettings:
    """How much real elevation to fetch, and how to contour it."""

    url_template: str = DEFAULT_TERRAIN_TILE_URL
    # Sampling width to aim for across the area. More pixels means finer
    # contours and more tiles to fetch.
    target_pixels: int = 1200
    max_tiles: int = 64
    max_zoom: int = MAX_SOURCE_ZOOM
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_delay_seconds: float = 0.7
    max_parallel_requests: int = 8
    # 0.0 chooses a round interval from the relief actually in view.
    contour_interval_metres: float = 0.0
    target_line_count: int = 60
    index_every: int = 5
    min_contour_length_cells: float = 2.0
    # Sub-sea contours are split off so the sea floor can be styled apart from
    # the land, or switched off entirely.
    separate_bathymetry: bool = True
    # Summits are labelled with their real height. A block this wide has to
    # contain the peak for it to count, which keeps a rough slope from
    # sprouting a label on every bump.
    summit_block_pixels: int = 96
    max_summits: int = 24
    min_summit_prominence_metres: float = 40.0
    # A high point on the sea floor is not a summit. Without this an ocean area
    # gets two dozen labelled "peaks" nobody can stand on.
    min_summit_elevation_metres: float = 1.0
    # Filled hypsometric bands. Broad areas, so they are traced on a decimated
    # copy of the grid: full resolution costs time and adds detail no fill can
    # show.
    emit_elevation_bands: bool = True
    elevation_band_count: int = 10
    band_grid_max_pixels: int = 520
    # Real DEMs carry step noise from their source resolution; one light pass
    # settles it without moving the landforms.
    smoothing_passes: int = 1
    # Relief shading, banded the same way elevation is. Off by default: it
    # changes the look of every sheet, which is a choice about the drawing
    # rather than a fact about the ground.
    emit_hillshade: bool = False
    hillshade_band_count: int = 7
    hillshade_grid_max_pixels: int = 420
    # A derivative carries several times the noise of the elevation it comes
    # from; smoothed after shading rather than before, or the bands speckle
    # into hundreds of one-cell polygons.
    hillshade_smoothing_passes: int = 2
    hillshade_sun_azimuth_degrees: float = 315.0
    hillshade_sun_altitude_degrees: float = 45.0
    hillshade_exaggeration: float = 1.0


@dataclass(slots=True)
class TerrainTileProvider:
    """Fetches and contours real elevation for the area."""

    settings: TerrainTileSettings = field(default_factory=TerrainTileSettings)
    http_get: HttpGetBytes | None = None
    # Set by the manager for a fetch that can be cancelled. Checked between
    # tiles, which is the only place this provider ever waits.
    cancel_check: Callable[[], bool] | None = None
    provider_id: str = TERRAIN_TILES_PROVIDER_ID
    label: str = TERRAIN_TILES_PROVIDER_LABEL
    source_path: Path | None = None

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            label=self.label,
            available=True,
            detail="Live public elevation tiles - real measured ground, no key needed",
        )

    def fetch_bbox(self, query: BBoxQuery) -> FeatureCollection:
        bounds = (query.min_lon, query.min_lat, query.max_lon, query.max_lat)
        zoom = _choose_zoom(bounds, self.settings)
        mosaic, origin = self._mosaic(bounds, zoom)
        grid, window = _crop_to_bounds(mosaic, origin, zoom, bounds)
        if grid.size == 0:
            raise TerrainTileError("Elevation tiles covered no part of the area")
        grid = _smooth(grid, self.settings.smoothing_passes)

        finite = grid[np.isfinite(grid)]
        lowest = float(finite.min()) if finite.size else 0.0
        highest = float(finite.max()) if finite.size else 0.0

        interval = self.settings.contour_interval_metres
        if interval <= 0.0:
            interval = nice_interval(highest - lowest, target_lines=self.settings.target_line_count)
        levels = contour_levels(lowest, highest, interval=interval, index_every=self.settings.index_every)

        to_lonlat = _lonlat_mapper(window, zoom)
        sample = _lonlat_sampler(grid, window, zoom)
        probe = _probe_step(window, zoom)

        features_by_layer = _empty_layers()
        for layer, layer_levels in (
            (MINOR_CONTOUR_LAYER, levels.minor),
            (INDEX_CONTOUR_LAYER, levels.index),
        ):
            for level in layer_levels:
                for polyline in contour_polylines(grid, level):
                    if _polyline_length(polyline) < self.settings.min_contour_length_cells:
                        continue
                    coordinates = [to_lonlat(row, col) for row, col in polyline]
                    if len(coordinates) < 2:
                        continue
                    coordinates = orient_uphill_left(coordinates, sample=sample, level=level, probe=probe)
                    target = layer
                    if self.settings.separate_bathymetry and level < 0.0:
                        target = BATHYMETRY_LAYER
                    features_by_layer[target].append(
                        {
                            "type": "Feature",
                            "id": f"{self.provider_id}/{target}/{level:.1f}/{len(features_by_layer[target])}",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[lon, lat] for lon, lat in coordinates],
                            },
                            "properties": {
                                "elevation": float(level),
                                "contour_interval": float(interval),
                                "index_contour": layer == INDEX_CONTOUR_LAYER,
                                "hipparchus_layer": target,
                                "hipparchus_source": self.provider_id,
                                "measured": True,
                            },
                        }
                    )

        if self.settings.emit_elevation_bands:
            features_by_layer[ELEVATION_BANDS_LAYER] = _band_features(
                grid,
                window,
                zoom,
                provider_id=self.provider_id,
                count=self.settings.elevation_band_count,
                max_pixels=self.settings.band_grid_max_pixels,
            )

        if self.settings.emit_hillshade:
            features_by_layer[HILLSHADE_LAYER] = _hillshade_features(
                grid,
                window,
                zoom,
                provider_id=self.provider_id,
                count=self.settings.hillshade_band_count,
                max_pixels=self.settings.hillshade_grid_max_pixels,
                sun=SunPosition(
                    azimuth_degrees=self.settings.hillshade_sun_azimuth_degrees,
                    altitude_degrees=self.settings.hillshade_sun_altitude_degrees,
                ),
                exaggeration=self.settings.hillshade_exaggeration,
                smoothing_passes=self.settings.hillshade_smoothing_passes,
            )

        features_by_layer[SUMMIT_LAYER] = _summit_features(
            grid,
            to_lonlat,
            provider_id=self.provider_id,
            block=self.settings.summit_block_pixels,
            limit=self.settings.max_summits,
            prominence=self.settings.min_summit_prominence_metres,
            min_elevation=self.settings.min_summit_elevation_metres,
        )

        return _collection_from_layers(
            features_by_layer,
            metadata={
                "source": self.provider_id,
                "format": "terrarium_tiles",
                "summit_count": len(features_by_layer[SUMMIT_LAYER]),
                "elevation_band_count": len(features_by_layer[ELEVATION_BANDS_LAYER]),
                "hillshade_band_count": len(features_by_layer[HILLSHADE_LAYER]),
                "measured": True,
                "zoom": zoom,
                "grid_shape": [int(grid.shape[0]), int(grid.shape[1])],
                "elevation_min_metres": lowest,
                "elevation_max_metres": highest,
                "contour_interval_metres": interval,
                "index_every": self.settings.index_every,
            },
            bbox=bounds,
        )

    def _mosaic(self, bounds: tuple[float, float, float, float], zoom: int) -> tuple[np.ndarray, tuple[int, int]]:
        min_lon, min_lat, max_lon, max_lat = bounds
        min_x, min_y = _tile_for(min_lon, max_lat, zoom)
        max_x, max_y = _tile_for(max_lon, min_lat, zoom)
        columns = max_x - min_x + 1
        rows = max_y - min_y + 1
        if columns * rows > self.settings.max_tiles:
            raise TerrainTileError(
                f"Area needs {columns * rows} elevation tiles at zoom {zoom}, over the {self.settings.max_tiles} limit"
            )

        mosaic = np.full((rows * TILE_PIXELS, columns * TILE_PIXELS), np.nan, dtype=float)
        # Tiles are independent network round trips, so fetching them one after
        # another spends the whole time waiting. A pool turns a 20-tile area
        # from half a minute into a few seconds.
        requests = [(row, column) for row in range(rows) for column in range(columns)]
        workers = max(1, min(self.settings.max_parallel_requests, len(requests)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._tile, zoom, min_x + column, min_y + row): (row, column)
                for row, column in requests
            }
            for future in as_completed(futures):
                if self.cancel_check is not None and self.cancel_check():
                    for pending in futures:
                        pending.cancel()
                    raise FetchCancelled("Elevation fetch cancelled")
                row, column = futures[future]
                tile = future.result()
                if tile is None:
                    continue
                mosaic[
                    row * TILE_PIXELS : (row + 1) * TILE_PIXELS,
                    column * TILE_PIXELS : (column + 1) * TILE_PIXELS,
                ] = tile
        if not np.isfinite(mosaic).any():
            raise TerrainTileError("No elevation tiles could be read for this area")
        return (mosaic, (min_x, min_y))

    def _tile(self, zoom: int, x: int, y: int) -> np.ndarray | None:
        url = self.settings.url_template.format(z=zoom, x=x, y=y)
        getter = self.http_get or _default_http_get_bytes
        attempts = max(1, int(self.settings.max_attempts))
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return _decode_terrarium(getter(url, self.settings.timeout_seconds))
            except Exception as exc:  # noqa: BLE001 - a missing tile is a hole, not a failure
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(self.settings.retry_delay_seconds * (attempt + 1))
        # One unavailable tile leaves a gap; the rest of the area still draws.
        _ = last_error
        return None


def terrain_tile_provider(
    settings: TerrainTileSettings | None = None,
    http_get: HttpGetBytes | None = None,
) -> TerrainTileProvider:
    return TerrainTileProvider(settings=settings or TerrainTileSettings(), http_get=http_get)


def _decode_terrarium(png_bytes: bytes) -> np.ndarray:
    """Unpack terrarium RGB into metres."""
    try:
        import skia  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise TerrainTileError(f"Decoding elevation tiles needs skia-python: {exc}") from exc

    image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(png_bytes))
    if image is None:
        raise TerrainTileError("Elevation tile is not a decodable image")
    pixels = np.asarray(image.toarray(), dtype=float)
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        raise TerrainTileError(f"Unexpected elevation tile shape: {pixels.shape}")
    return pixels[:, :, 0] * 256.0 + pixels[:, :, 1] + pixels[:, :, 2] / 256.0 - 32768.0


def _choose_zoom(bounds: tuple[float, float, float, float], settings: TerrainTileSettings) -> int:
    """Highest zoom that samples the area finely without over-fetching tiles."""
    min_lon, min_lat, max_lon, max_lat = bounds
    lon_span = max(1e-9, abs(max_lon - min_lon))
    for zoom in range(min(settings.max_zoom, MAX_SOURCE_ZOOM), -1, -1):
        pixels_across = lon_span / 360.0 * (2**zoom) * TILE_PIXELS
        if pixels_across > settings.target_pixels:
            continue
        min_x, min_y = _tile_for(min_lon, max_lat, zoom)
        max_x, max_y = _tile_for(max_lon, min_lat, zoom)
        if (max_x - min_x + 1) * (max_y - min_y + 1) <= settings.max_tiles:
            return zoom
    return 0


def _tile_for(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    lat = max(-85.05112878, min(85.05112878, lat))
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return (max(0, min(n - 1, x)), max(0, min(n - 1, y)))


def _pixel_for(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    """Global pixel coordinates, fractional."""
    world = (2**zoom) * TILE_PIXELS
    lat = max(-85.05112878, min(85.05112878, lat))
    x = (lon + 180.0) / 360.0 * world
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * world
    return (x, y)


def _lonlat_for_pixel(x: float, y: float, zoom: int) -> tuple[float, float]:
    world = (2**zoom) * TILE_PIXELS
    lon = x / world * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / world))))
    return (lon, lat)


@dataclass(slots=True, frozen=True)
class _Window:
    """Where the cropped grid sits in the mosaic's global pixel space."""

    left: int
    top: int
    width: int
    height: int


def _crop_to_bounds(
    mosaic: np.ndarray,
    origin: tuple[int, int],
    zoom: int,
    bounds: tuple[float, float, float, float],
) -> tuple[np.ndarray, _Window]:
    min_lon, min_lat, max_lon, max_lat = bounds
    origin_x = origin[0] * TILE_PIXELS
    origin_y = origin[1] * TILE_PIXELS

    left_global, top_global = _pixel_for(min_lon, max_lat, zoom)
    right_global, bottom_global = _pixel_for(max_lon, min_lat, zoom)

    left = max(0, int(math.floor(left_global - origin_x)))
    top = max(0, int(math.floor(top_global - origin_y)))
    right = min(mosaic.shape[1], int(math.ceil(right_global - origin_x)))
    bottom = min(mosaic.shape[0], int(math.ceil(bottom_global - origin_y)))
    if right - left < 2 or bottom - top < 2:
        return (np.empty((0, 0)), _Window(0, 0, 0, 0))

    grid = mosaic[top:bottom, left:right]
    window = _Window(left=origin_x + left, top=origin_y + top, width=grid.shape[1], height=grid.shape[0])
    return (grid, window)


def _lonlat_mapper(window: _Window, zoom: int) -> Callable[[float, float], tuple[float, float]]:
    def to_lonlat(row: float, col: float) -> tuple[float, float]:
        return _lonlat_for_pixel(window.left + col, window.top + row, zoom)

    return to_lonlat


def _lonlat_sampler(grid: np.ndarray, window: _Window, zoom: int) -> Callable[[float, float], float]:
    height, width = grid.shape

    def sample(lon: float, lat: float) -> float:
        x, y = _pixel_for(lon, lat, zoom)
        col = int(min(max(round(x - window.left), 0), width - 1))
        row = int(min(max(round(y - window.top), 0), height - 1))
        value = grid[row, col]
        return float(value) if math.isfinite(value) else float("nan")

    return sample


def _probe_step(window: _Window, zoom: int) -> float:
    """One pixel, expressed in degrees of longitude."""
    world = (2**zoom) * TILE_PIXELS
    return max(1e-12, 360.0 / world)


def _ground_resolution_metres(lat_degrees: float, zoom: int) -> float:
    """Metres a single tile pixel spans at this latitude and zoom.

    Web Mercator stretches east-west scale by ``1 / cos(latitude)`` to stay
    conformal, so a pixel near a pole covers less ground than one at the
    equator. Hillshade needs the real spacing to get slope right -- a fixed
    metres-per-pixel hardens the same mountain every time the zoom steps up.
    """
    world = (2**zoom) * TILE_PIXELS
    lat = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat_degrees))
    return math.cos(math.radians(lat)) * (2.0 * math.pi * EARTH_RADIUS_M) / world


def _smooth(grid: np.ndarray, passes: int) -> np.ndarray:
    if passes <= 0 or grid.size == 0:
        return grid
    valid = np.isfinite(grid)
    filled = np.where(valid, grid, 0.0)
    weight = valid.astype(float)
    for _ in range(int(passes)):
        filled = _box_blur(filled)
        weight = _box_blur(weight)
    with np.errstate(divide="ignore", invalid="ignore"):
        blurred = np.where(weight > 0.0, filled / weight, np.nan)
    return np.where(valid, blurred, np.nan)


def _box_blur(values: np.ndarray) -> np.ndarray:
    padded = np.pad(values, 1, mode="edge")
    horizontal = (padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]) / 3.0
    return (horizontal[:-2, :] + horizontal[1:-1, :] + horizontal[2:, :]) / 3.0


def _band_features(
    grid: np.ndarray,
    window: "_Window",
    zoom: int,
    *,
    provider_id: str,
    count: int,
    max_pixels: int,
) -> list[dict[str, Any]]:
    """Filled hypsometric bands, low to high."""
    if count < 2:
        return []

    step = max(1, int(math.ceil(max(grid.shape) / max(16, max_pixels))))
    coarse = grid[::step, ::step]
    finite = coarse[np.isfinite(coarse)]
    if finite.size == 0:
        return []

    boundaries = band_boundaries(float(finite.min()), float(finite.max()), count)
    bands = elevation_bands(coarse, boundaries)
    if not bands:
        return []

    def to_lonlat(row: float, col: float) -> tuple[float, float]:
        # Decimation changes the index scale, not the geography.
        return _lonlat_for_pixel(window.left + col * step, window.top + row * step, zoom)

    features: list[dict[str, Any]] = []
    for index, band in enumerate(bands):
        geometry = map_coordinates(band.geometry, to_lonlat)
        if geometry.is_empty:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"{provider_id}/{ELEVATION_BANDS_LAYER}/{index}",
                "geometry": mapping(geometry),
                "properties": {
                    "elevation_low": band.lower,
                    "elevation_high": band.upper,
                    "band_index": index,
                    "band_count": len(bands),
                    "hipparchus_layer": ELEVATION_BANDS_LAYER,
                    "hipparchus_source": provider_id,
                    "measured": True,
                },
            }
        )
    return features


def _hillshade_features(
    grid: np.ndarray,
    window: "_Window",
    zoom: int,
    *,
    provider_id: str,
    count: int,
    max_pixels: int,
    sun: SunPosition,
    exaggeration: float,
    smoothing_passes: int,
) -> list[dict[str, Any]]:
    """Relief shading, filled and banded the way the elevation bands are.

    Banded on a **fixed** 0...1 scale, not the observed range of light and
    shadow actually in the tile. Stretching the observed range sounds right --
    gentle ground never reaches either extreme -- but it turns "how much
    relief is there" into "always maximum contrast", and flat or nearly flat
    ground mottles into a texture that reads as terrain and is not.
    """
    if count < 2:
        return []

    step = max(1, int(math.ceil(max(grid.shape) / max(16, max_pixels))))
    coarse = grid[::step, ::step]
    if coarse.size == 0 or not np.isfinite(coarse).any():
        return []

    centre_row = window.top + (coarse.shape[0] * step) / 2.0
    centre_col = window.left + (coarse.shape[1] * step) / 2.0
    _, centre_lat = _lonlat_for_pixel(centre_col, centre_row, zoom)
    cell_size_metres = _ground_resolution_metres(centre_lat, zoom) * step

    illumination = hillshade(coarse, sun=sun, cell_size_metres=cell_size_metres, exaggeration=exaggeration)
    illumination = _smooth(illumination, smoothing_passes)

    boundaries = band_boundaries(0.0, 1.0, count)
    bands = elevation_bands(illumination, boundaries)
    if not bands:
        return []

    def to_lonlat(row: float, col: float) -> tuple[float, float]:
        # Decimation changes the index scale, not the geography.
        return _lonlat_for_pixel(window.left + col * step, window.top + row * step, zoom)

    features: list[dict[str, Any]] = []
    for band in bands:
        geometry = map_coordinates(band.geometry, to_lonlat)
        if geometry.is_empty:
            continue
        # The band's place on the fixed scale, not in this (possibly
        # compacted) list: `elevation_bands` drops any band the illumination
        # never reaches, and a band index taken from list position would put
        # ground that only ever reaches two adjacent tones at the ramp's two
        # extremes -- the stretching above, moved one step downstream.
        index = int(round(band.lower * count))
        features.append(
            {
                "type": "Feature",
                "id": f"{provider_id}/{HILLSHADE_LAYER}/{index}",
                "geometry": mapping(geometry),
                "properties": {
                    "shade_low": band.lower,
                    "shade_high": band.upper,
                    "band_index": index,
                    "band_count": count,
                    "sun_azimuth": sun.azimuth_degrees,
                    "sun_altitude": sun.altitude_degrees,
                    "hipparchus_layer": HILLSHADE_LAYER,
                    "hipparchus_source": provider_id,
                    "measured": True,
                },
            }
        )
    return features


def _summit_features(
    grid: np.ndarray,
    to_lonlat: Callable[[float, float], tuple[float, float]],
    *,
    provider_id: str,
    block: int,
    limit: int,
    prominence: float,
    min_elevation: float,
) -> list[dict[str, Any]]:
    """Label the highest ground, with the height actually measured there.

    A contour sheet tells you the shape but never the number. Taking the maximum
    of each block, and keeping only blocks that stand clear of their own
    surroundings, puts a real height on the peaks without labelling every bump
    on a slope.
    """
    height, width = grid.shape
    if height < block or width < block or limit <= 0:
        return []

    candidates: list[tuple[float, int, int]] = []
    for top in range(0, height - block + 1, block):
        for left in range(0, width - block + 1, block):
            window = grid[top : top + block, left : left + block]
            finite = window[np.isfinite(window)]
            if finite.size == 0:
                continue
            peak = float(finite.max())
            if peak < min_elevation:
                continue
            # A block whose peak barely stands above its own floor is a slope,
            # not a summit.
            if peak - float(finite.min()) < prominence:
                continue
            row, col = np.unravel_index(int(np.nanargmax(window)), window.shape)
            candidates.append((peak, top + int(row), left + int(col)))

    candidates.sort(reverse=True)
    features: list[dict[str, Any]] = []
    for peak, row, col in candidates[:limit]:
        lon, lat = to_lonlat(float(row), float(col))
        features.append(
            {
                "type": "Feature",
                "id": f"{provider_id}/summit/{len(features)}",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": f"{peak:.0f} m",
                    "elevation": peak,
                    "hipparchus_layer": SUMMIT_LAYER,
                    "hipparchus_source": provider_id,
                    "measured": True,
                },
            }
        )
    return features


def _polyline_length(polyline: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(next_row - row, next_col - col)
        for (row, col), (next_row, next_col) in zip(polyline, polyline[1:])
    )


def _default_http_get_bytes(url: str, timeout_seconds: float) -> bytes:
    from urllib.request import Request, urlopen

    request = Request(url, method="GET")
    request.add_header("User-Agent", "Hipparchus/0.3 (online map generator)")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read()


__all__ = [
    "DEFAULT_TERRAIN_TILE_URL",
    "TERRAIN_TILES_PROVIDER_ID",
    "ELEVATION_BANDS_LAYER",
    "HILLSHADE_LAYER",
    "TerrainTileError",
    "TerrainTileSettings",
    "TerrainTileProvider",
    "terrain_tile_provider",
]
