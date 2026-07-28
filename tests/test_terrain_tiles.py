"""Tests for real elevation from public terrain tiles."""

from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

try:
    import skia  # type: ignore  # noqa: F401

    SKIA_AVAILABLE = True
except Exception:  # noqa: BLE001
    SKIA_AVAILABLE = False

from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.terrain_tiles import (
    TILE_PIXELS,
    TerrainTileError,
    TerrainTileSettings,
    _choose_zoom,
    _decode_terrarium,
    _lonlat_for_pixel,
    _pixel_for,
    _tile_for,
    terrain_tile_provider,
)


ATHENS = BBoxQuery(min_lon=23.57, min_lat=37.81, max_lon=23.89, max_lat=38.13)


def _terrarium_png(elevations: np.ndarray) -> bytes:
    """Encode metres back into terrarium RGB, the inverse of the decoder."""
    import skia  # type: ignore

    raw = np.clip(elevations + 32768.0, 0.0, 65535.0)
    red = np.floor(raw / 256.0)
    green = np.floor(raw - red * 256.0)
    blue = np.floor((raw - red * 256.0 - green) * 256.0)
    pixels = np.zeros((*elevations.shape, 4), dtype=np.uint8)
    pixels[:, :, 0] = red.astype(np.uint8)
    pixels[:, :, 1] = green.astype(np.uint8)
    pixels[:, :, 2] = blue.astype(np.uint8)
    pixels[:, :, 3] = 255
    image = skia.Image.fromarray(np.ascontiguousarray(pixels), skia.kRGBA_8888_ColorType)
    return bytes(image.encodeToData())


def _ramp_tile() -> bytes:
    """A tile rising smoothly west to east, 0 m to 1000 m."""
    ramp = np.linspace(0.0, 1000.0, TILE_PIXELS)
    return _terrarium_png(np.tile(ramp, (TILE_PIXELS, 1)))


class ProjectionTests(unittest.TestCase):
    """Tiles are Web Mercator; treating rows as evenly spaced in latitude
    displaces every contour, more so the further from the equator."""

    def test_pixel_and_lonlat_round_trip(self) -> None:
        for lon, lat in ((23.75, 37.96), (-122.4, 37.8), (11.0, 60.0), (0.0, 0.0), (150.0, -33.9)):
            with self.subTest(lon=lon, lat=lat):
                x, y = _pixel_for(lon, lat, 12)
                back_lon, back_lat = _lonlat_for_pixel(x, y, 12)
                self.assertAlmostEqual(back_lon, lon, places=6)
                self.assertAlmostEqual(back_lat, lat, places=6)

    def test_latitude_spacing_is_not_linear(self) -> None:
        """The bug this guards: a linear row-to-latitude map."""
        zoom = 10
        world = (2**zoom) * TILE_PIXELS
        near_equator = _lonlat_for_pixel(0.0, world / 2.0, zoom)[1] - _lonlat_for_pixel(0.0, world / 2.0 + 100.0, zoom)[1]
        far_north = _lonlat_for_pixel(0.0, world * 0.25, zoom)[1] - _lonlat_for_pixel(0.0, world * 0.25 + 100.0, zoom)[1]
        self.assertGreater(near_equator, far_north * 1.5)

    def test_tile_indices_match_the_published_scheme(self) -> None:
        # Athens at zoom 11 is tile 1159/790 in the XYZ scheme.
        self.assertEqual(_tile_for(23.75, 37.96, 11), (1159, 790))

    def test_tiles_are_clamped_to_the_world(self) -> None:
        self.assertEqual(_tile_for(-181.0, 89.0, 3)[0], 0)
        self.assertEqual(_tile_for(181.0, -89.0, 3)[0], 7)


class ZoomChoiceTests(unittest.TestCase):
    def test_a_small_area_is_sampled_more_finely_than_a_large_one(self) -> None:
        city = _choose_zoom((23.70, 37.95, 23.80, 38.02), TerrainTileSettings())
        region = _choose_zoom((20.0, 34.0, 29.0, 41.0), TerrainTileSettings())
        self.assertGreater(city, region)

    def test_the_tile_budget_is_respected(self) -> None:
        settings = TerrainTileSettings(max_tiles=4)
        bounds = (23.0, 37.0, 24.0, 38.0)
        zoom = _choose_zoom(bounds, settings)
        min_x, min_y = _tile_for(bounds[0], bounds[3], zoom)
        max_x, max_y = _tile_for(bounds[2], bounds[1], zoom)
        self.assertLessEqual((max_x - min_x + 1) * (max_y - min_y + 1), 4)


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class TerrariumDecodeTests(unittest.TestCase):
    def test_known_elevations_survive_a_round_trip(self) -> None:
        original = np.array([[0.0, 100.0], [-50.0, 8848.0]])
        decoded = _decode_terrarium(_terrarium_png(original))
        np.testing.assert_allclose(decoded, original, atol=0.01)

    def test_sea_level_and_below_decode_correctly(self) -> None:
        decoded = _decode_terrarium(_terrarium_png(np.array([[0.0, -430.0]])))
        self.assertAlmostEqual(decoded[0, 0], 0.0, places=2)
        self.assertAlmostEqual(decoded[0, 1], -430.0, places=2)

    def test_a_non_image_response_is_reported(self) -> None:
        with self.assertRaises(TerrainTileError):
            _decode_terrarium(b"<Error><Code>NoSuchKey</Code></Error>")


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class FetchTests(unittest.TestCase):
    def _provider(self, settings: TerrainTileSettings | None = None, capture: list | None = None):
        def fake_get(url: str, timeout: float) -> bytes:
            if capture is not None:
                capture.append(url)
            return _ramp_tile()

        return terrain_tile_provider(settings or TerrainTileSettings(max_tiles=8, target_pixels=512), fake_get)

    def test_contours_are_produced_from_real_metres(self) -> None:
        result = self._provider().fetch_bbox(ATHENS)
        features = result.features_by_layer["terrain_contours"]
        self.assertTrue(features)
        for feature in features:
            self.assertEqual(feature["geometry"]["type"], "LineString")
            self.assertTrue(feature["properties"]["measured"])

    def test_metadata_reports_measured_ground(self) -> None:
        metadata = self._provider().fetch_bbox(ATHENS).metadata
        self.assertTrue(metadata["measured"])
        self.assertEqual(metadata["source"], "terrain_tiles")
        self.assertIn("zoom", metadata)
        self.assertGreater(metadata["elevation_max_metres"], metadata["elevation_min_metres"])

    def test_contours_stay_inside_the_area(self) -> None:
        result = self._provider().fetch_bbox(ATHENS)
        for feature in result.features_by_layer["terrain_contours"][:40]:
            for lon, lat in feature["geometry"]["coordinates"]:
                self.assertGreaterEqual(lon, ATHENS.min_lon - 0.01)
                self.assertLessEqual(lon, ATHENS.max_lon + 0.01)
                self.assertGreaterEqual(lat, ATHENS.min_lat - 0.01)
                self.assertLessEqual(lat, ATHENS.max_lat + 0.01)

    def test_elevations_sit_on_the_contour_interval(self) -> None:
        result = self._provider().fetch_bbox(ATHENS)
        interval = float(result.metadata["contour_interval_metres"])
        for feature in result.features_by_layer["terrain_contours"]:
            self.assertAlmostEqual(float(feature["properties"]["elevation"]) % interval, 0.0, places=6)

    def test_the_url_template_is_filled_in(self) -> None:
        capture: list = []
        self._provider(capture=capture).fetch_bbox(ATHENS)
        self.assertTrue(capture)
        for url in capture:
            self.assertTrue(url.startswith("https://"))
            self.assertTrue(url.endswith(".png"))
            self.assertNotIn("{z}", url)

    def test_a_missing_tile_leaves_a_hole_rather_than_failing(self) -> None:
        """One unavailable tile must not lose the rest of the area."""
        calls: list[int] = []

        def flaky(url: str, timeout: float) -> bytes:
            calls.append(1)
            if len(calls) == 1:
                raise OSError("404")
            return _ramp_tile()

        settings = TerrainTileSettings(max_tiles=8, target_pixels=512, max_attempts=1)
        result = terrain_tile_provider(settings, flaky).fetch_bbox(ATHENS)
        self.assertTrue(result.features_by_layer["terrain_contours"])

    def test_every_tile_failing_is_reported(self) -> None:
        def broken(url: str, timeout: float) -> bytes:
            raise OSError("no route to host")

        settings = TerrainTileSettings(max_tiles=8, target_pixels=512, max_attempts=1)
        with self.assertRaises(TerrainTileError):
            terrain_tile_provider(settings, broken).fetch_bbox(ATHENS)

    def test_an_oversized_area_is_refused_rather_than_hammering_the_service(self) -> None:
        settings = TerrainTileSettings(max_tiles=2, target_pixels=4096, max_zoom=14)
        provider = terrain_tile_provider(settings, lambda url, timeout: _ramp_tile())
        # Zoom selection already respects the budget, so this checks the guard
        # inside the mosaic builder using a zoom that cannot possibly fit.
        with self.assertRaises(TerrainTileError):
            provider._mosaic((0.0, 0.0, 40.0, 40.0), 8)

    def test_summits_are_labelled_with_their_measured_height(self) -> None:
        summits = self._provider().fetch_bbox(ATHENS).features_by_layer["summits"]
        for feature in summits:
            self.assertEqual(feature["geometry"]["type"], "Point")
            self.assertTrue(feature["properties"]["name"].endswith(" m"))
            self.assertTrue(feature["properties"]["measured"])

    def test_the_sea_floor_grows_no_summits(self) -> None:
        """A high point on the sea floor is not a peak anyone can stand on."""
        drowned = _terrarium_png(np.tile(np.linspace(-1200.0, -40.0, TILE_PIXELS), (TILE_PIXELS, 1)))
        settings = TerrainTileSettings(max_tiles=8, target_pixels=512)
        result = terrain_tile_provider(settings, lambda url, timeout: drowned).fetch_bbox(ATHENS)
        self.assertEqual(result.features_by_layer["summits"], [])

    def test_sub_sea_contours_are_kept_apart_from_land(self) -> None:
        below = _terrarium_png(np.tile(np.linspace(-800.0, 400.0, TILE_PIXELS), (TILE_PIXELS, 1)))
        settings = TerrainTileSettings(max_tiles=8, target_pixels=512)
        result = terrain_tile_provider(settings, lambda url, timeout: below).fetch_bbox(ATHENS)

        self.assertTrue(result.features_by_layer["bathymetry"])
        self.assertTrue(result.features_by_layer["terrain_contours"])
        for feature in result.features_by_layer["bathymetry"]:
            self.assertLess(feature["properties"]["elevation"], 0.0)
        for feature in result.features_by_layer["terrain_contours"]:
            self.assertGreater(feature["properties"]["elevation"], 0.0)

    def test_bathymetry_can_be_folded_back_into_the_terrain_layer(self) -> None:
        below = _terrarium_png(np.tile(np.linspace(-800.0, 400.0, TILE_PIXELS), (TILE_PIXELS, 1)))
        settings = TerrainTileSettings(max_tiles=8, target_pixels=512, separate_bathymetry=False)
        result = terrain_tile_provider(settings, lambda url, timeout: below).fetch_bbox(ATHENS)
        self.assertEqual(result.features_by_layer["bathymetry"], [])

    def test_filled_elevation_bands_are_produced(self) -> None:
        result = self._provider().fetch_bbox(ATHENS)
        bands = result.features_by_layer["elevation_bands"]
        self.assertTrue(bands)
        for feature in bands:
            self.assertIn(feature["geometry"]["type"], {"Polygon", "MultiPolygon"})
            properties = feature["properties"]
            self.assertLess(properties["elevation_low"], properties["elevation_high"])
            self.assertTrue(properties["measured"])

    def test_bands_are_ordered_and_indexed_for_the_ramp(self) -> None:
        bands = self._provider().fetch_bbox(ATHENS).features_by_layer["elevation_bands"]
        indices = [f["properties"]["band_index"] for f in bands]
        self.assertEqual(indices, sorted(indices))
        for feature in bands:
            self.assertEqual(feature["properties"]["band_count"], len(bands))

    def test_bands_can_be_switched_off(self) -> None:
        settings = TerrainTileSettings(max_tiles=8, target_pixels=512, emit_elevation_bands=False)
        result = terrain_tile_provider(settings, lambda url, timeout: _ramp_tile()).fetch_bbox(ATHENS)
        self.assertEqual(result.features_by_layer["elevation_bands"], [])

    def test_the_provider_reports_itself_available(self) -> None:
        status = terrain_tile_provider().status()
        self.assertTrue(status.available)
        self.assertEqual(status.provider_id, "terrain_tiles")


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class ReliefOverlayTests(unittest.TestCase):
    """Relief has to be addable to any model, not only to its own."""

    def test_extra_providers_are_merged_into_any_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            manager._optional_providers["terrain_tiles"] = terrain_tile_provider(
                TerrainTileSettings(max_tiles=8, target_pixels=512),
                lambda url, timeout: _ramp_tile(),
            )
            payload = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": [[23.6, 37.9], [23.7, 38.0]]},
                        "properties": {"hipparchus_layer": "roads", "name": "Test Street"},
                    }
                ],
            }
            import json

            source = Path(tmp) / "roads.geojson"
            source.write_text(json.dumps(payload), encoding="utf-8")
            manager.set_optional_source_path("vector_tiles", source)

            result = manager.fetch_map_model(ATHENS, "vector_tiles", extra_provider_ids=("terrain_tiles",))

        # Both sources present: the model's own roads and the added relief.
        self.assertTrue(result.features_by_layer["roads"])
        self.assertTrue(result.features_by_layer["terrain_contours"])
        self.assertIn("terrain_tiles", result.metadata["sources"])
        self.assertIn("vector_tiles", result.metadata["sources"])

    def test_a_model_that_already_has_relief_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            manager._optional_providers["terrain_tiles"] = terrain_tile_provider(
                TerrainTileSettings(max_tiles=8, target_pixels=512),
                lambda url, timeout: _ramp_tile(),
            )
            result = manager.fetch_map_model(ATHENS, "terrain_online", extra_provider_ids=("terrain_tiles",))

        self.assertEqual(result.metadata["sources"], ["terrain_tiles"])


class MercatorSanityTests(unittest.TestCase):
    def test_a_contour_at_athens_latitude_is_not_displaced(self) -> None:
        """A linear row-to-latitude map would place this several hundred metres out."""
        zoom = 12
        _x, y = _pixel_for(23.75, 38.00, zoom)
        # Half a pixel south should be a small, latitude-correct step.
        step = _lonlat_for_pixel(0.0, y, zoom)[1] - _lonlat_for_pixel(0.0, y + 0.5, zoom)[1]
        expected = 360.0 / ((2**zoom) * TILE_PIXELS) * 0.5 * math.cos(math.radians(38.0))
        self.assertAlmostEqual(step, expected, places=6)


if __name__ == "__main__":
    unittest.main()
