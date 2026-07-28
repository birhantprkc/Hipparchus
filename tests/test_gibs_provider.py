"""Tests for the online NASA GIBS imagery provider."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

import numpy as np

try:
    import skia  # type: ignore  # noqa: F401

    SKIA_AVAILABLE = True
except Exception:  # noqa: BLE001
    SKIA_AVAILABLE = False

from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.gibs_provider import (
    NIGHT_LIGHTS_LAYER,
    SatelliteImageryError,
    SatelliteImagerySettings,
    _image_size,
    _levels_between,
    gibs_imagery_provider,
)
from hipparchus.data_sources.provider import BBoxQuery


ATHENS = BBoxQuery(min_lon=23.60, min_lat=37.90, max_lon=23.84, max_lat=38.08)


def _png(pixels: np.ndarray) -> bytes:
    """Encode an HxWx4 uint8 array as PNG through skia."""
    import skia  # type: ignore

    image = skia.Image.fromarray(np.ascontiguousarray(pixels.astype(np.uint8)), skia.kRGBA_8888_ColorType)
    return bytes(image.encodeToData())


def _gradient_png(width: int = 64, height: int = 48) -> bytes:
    """A left-to-right brightness ramp: contours must come out as vertical lines."""
    ramp = np.linspace(0, 255, width)
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    for channel in range(3):
        pixels[:, :, channel] = ramp[None, :]
    pixels[:, :, 3] = 255
    return _png(pixels)


def _flat_png(value: int = 255, width: int = 32, height: int = 32) -> bytes:
    pixels = np.full((height, width, 4), value, dtype=np.uint8)
    pixels[:, :, 3] = 255
    return _png(pixels)


class RequestTests(unittest.TestCase):
    def test_the_wms_request_uses_lat_lon_bbox_order(self) -> None:
        """WMS 1.3.0 orders EPSG:4326 lat,lon -- reversing it maps somewhere else."""
        capture: list = []

        def fake_get(url: str, timeout: float) -> bytes:
            capture.append(url)
            return _flat_png()

        gibs_imagery_provider(http_get=fake_get).fetch_bbox(ATHENS)

        query = parse_qs(urlparse(capture[0]).query)
        self.assertEqual(query["VERSION"], ["1.3.0"])
        self.assertEqual(query["CRS"], ["EPSG:4326"])
        self.assertEqual(query["BBOX"], ["37.9,23.6,38.08,23.84"])
        self.assertEqual(query["LAYERS"], ["VIIRS_Black_Marble"])
        self.assertEqual(query["FORMAT"], ["image/png"])

    def test_a_date_is_only_sent_when_configured(self) -> None:
        capture: list = []

        def fake_get(url: str, timeout: float) -> bytes:
            capture.append(url)
            return _flat_png()

        gibs_imagery_provider(SatelliteImagerySettings(), fake_get).fetch_bbox(ATHENS)
        gibs_imagery_provider(SatelliteImagerySettings(date="2024-01-15"), fake_get).fetch_bbox(ATHENS)

        self.assertNotIn("TIME", parse_qs(urlparse(capture[0]).query))
        self.assertEqual(parse_qs(urlparse(capture[1]).query)["TIME"], ["2024-01-15"])

    def test_a_failed_request_is_reported_as_an_imagery_error(self) -> None:
        def broken(url: str, timeout: float) -> bytes:
            raise OSError("no route to host")

        provider = gibs_imagery_provider(SatelliteImagerySettings(max_attempts=1), broken)
        with self.assertRaises(SatelliteImageryError):
            provider.fetch_bbox(ATHENS)

    def test_a_transient_failure_is_retried(self) -> None:
        """GIBS was observed answering 500 once and then serving the same request."""
        attempts: list[int] = []

        def flaky(url: str, timeout: float) -> bytes:
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError("HTTP Error 500: Internal Server Error")
            return _flat_png()

        settings = SatelliteImagerySettings(max_attempts=3, retry_delay_seconds=0.0)
        gibs_imagery_provider(settings, flaky).fetch_bbox(ATHENS)
        self.assertEqual(len(attempts), 2)

    def test_retries_are_bounded(self) -> None:
        attempts: list[int] = []

        def always_broken(url: str, timeout: float) -> bytes:
            attempts.append(1)
            raise OSError("down")

        settings = SatelliteImagerySettings(max_attempts=3, retry_delay_seconds=0.0)
        with self.assertRaises(SatelliteImageryError):
            gibs_imagery_provider(settings, always_broken).fetch_bbox(ATHENS)
        self.assertEqual(len(attempts), 3)

    def test_an_undecodable_response_is_reported(self) -> None:
        with self.assertRaises(SatelliteImageryError):
            gibs_imagery_provider(
                SatelliteImagerySettings(max_attempts=1),
                lambda url, timeout: b"<html>error</html>",
            ).fetch_bbox(ATHENS)

    def test_the_provider_reports_itself_available_and_uncalibrated(self) -> None:
        status = gibs_imagery_provider().status()
        self.assertTrue(status.available)
        self.assertIn("not calibrated", status.detail)


class ImageSizeTests(unittest.TestCase):
    def test_the_request_matches_the_aoi_aspect(self) -> None:
        width, height = _image_size((0.0, 0.0, 4.0, 2.0), 1000)
        self.assertEqual((width, height), (1000, 500))
        width, height = _image_size((0.0, 0.0, 1.0, 4.0), 1000)
        self.assertEqual((width, height), (250, 1000))

    def test_a_degenerate_aoi_is_safe(self) -> None:
        self.assertEqual(_image_size((5.0, 5.0, 5.0, 5.0), 256), (256, 256))


class LevelTests(unittest.TestCase):
    def test_levels_split_the_observed_range(self) -> None:
        self.assertEqual(_levels_between(0.0, 100.0, 4), [20.0, 40.0, 60.0, 80.0])

    def test_a_flat_image_has_no_levels(self) -> None:
        self.assertEqual(_levels_between(255.0, 255.0, 8), [])


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class ContourTests(unittest.TestCase):
    def test_a_brightness_ramp_becomes_iso_lines(self) -> None:
        result = gibs_imagery_provider(http_get=lambda url, timeout: _gradient_png()).fetch_bbox(ATHENS)
        features = result.features_by_layer[NIGHT_LIGHTS_LAYER]
        self.assertTrue(features)
        for feature in features:
            self.assertEqual(feature["geometry"]["type"], "LineString")
            longitudes = {round(point[0], 6) for point in feature["geometry"]["coordinates"]}
            # A left-to-right ramp contours into lines of constant longitude.
            self.assertEqual(len(longitudes), 1)

    def test_contours_carry_the_uncalibrated_warning(self) -> None:
        result = gibs_imagery_provider(http_get=lambda url, timeout: _gradient_png()).fetch_bbox(ATHENS)
        properties = result.features_by_layer[NIGHT_LIGHTS_LAYER][0]["properties"]
        self.assertFalse(properties["calibrated"])
        self.assertEqual(properties["hipparchus_layer"], NIGHT_LIGHTS_LAYER)
        self.assertIn("brightness", properties)

    def test_a_saturated_window_is_reported_rather_than_silently_empty(self) -> None:
        """A city core clips to white, and clipped pixels have no contours."""
        result = gibs_imagery_provider(http_get=lambda url, timeout: _flat_png(255)).fetch_bbox(ATHENS)
        self.assertTrue(result.metadata["saturated"])
        self.assertEqual(result.features_by_layer[NIGHT_LIGHTS_LAYER], [])

    def test_metadata_never_claims_calibration(self) -> None:
        metadata = gibs_imagery_provider(http_get=lambda url, timeout: _gradient_png()).fetch_bbox(ATHENS).metadata
        self.assertFalse(metadata["calibrated"])
        self.assertEqual(metadata["gibs_layer"], "VIIRS_Black_Marble")


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class ManagerIntegrationTests(unittest.TestCase):
    def test_the_online_night_lights_model_is_fetchable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            manager._optional_providers["gibs_imagery"] = gibs_imagery_provider(
                http_get=lambda url, timeout: _gradient_png()
            )
            result = manager.fetch_map_model(ATHENS, "night_lights_online")

        self.assertEqual(result.metadata["model"], "night_lights_online")
        self.assertTrue(result.features_by_layer[NIGHT_LIGHTS_LAYER])


if __name__ == "__main__":
    unittest.main()
