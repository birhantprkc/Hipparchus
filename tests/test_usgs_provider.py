"""Tests for the live USGS seismicity provider."""

from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.usgs_provider import (
    DEEP_LAYER,
    INTERMEDIATE_LAYER,
    SHALLOW_LAYER,
    SeismicityRequestError,
    SeismicitySettings,
    usgs_earthquake_provider,
)


AEGEAN = BBoxQuery(min_lon=20.0, min_lat=34.0, max_lon=29.0, max_lat=41.0)


def _event(
    *,
    lon: float = 25.0,
    lat: float = 37.0,
    depth_km: float = 10.0,
    magnitude: float | None = 5.4,
    identifier: str = "us1234",
    place: str = "12 km SW of Nowhere",
    time_ms: int = 1_700_000_000_000,
) -> dict:
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth_km]},
        "properties": {"mag": magnitude, "place": place, "time": time_ms, "url": "https://example.invalid"},
    }


def _provider(events: list[dict], settings: SeismicitySettings | None = None, capture: list | None = None):
    def fake_get(url: str, timeout: float) -> dict:
        if capture is not None:
            capture.append((url, timeout))
        return {"type": "FeatureCollection", "features": events}

    return usgs_earthquake_provider(settings, http_get=fake_get)


class RequestTests(unittest.TestCase):
    def test_the_query_asks_for_the_aoi_and_the_configured_filters(self) -> None:
        capture: list = []
        _provider([], SeismicitySettings(days=90, min_magnitude=3.5, limit=500), capture).fetch_bbox(AEGEAN)

        url, _timeout = capture[0]
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["format"], ["geojson"])
        self.assertEqual(float(query["minlongitude"][0]), 20.0)
        self.assertEqual(float(query["maxlatitude"][0]), 41.0)
        self.assertEqual(query["minmagnitude"], ["3.5"])
        self.assertEqual(query["limit"], ["500"])
        self.assertIn("starttime", query)
        self.assertIn("endtime", query)

    def test_a_failed_request_is_reported_as_a_seismicity_error(self) -> None:
        def broken_get(url: str, timeout: float) -> dict:
            raise OSError("network down")

        provider = usgs_earthquake_provider(http_get=broken_get)
        with self.assertRaises(SeismicityRequestError):
            provider.fetch_bbox(AEGEAN)

    def test_the_provider_reports_itself_available(self) -> None:
        status = usgs_earthquake_provider().status()
        self.assertTrue(status.available)
        self.assertEqual(status.provider_id, "usgs_earthquakes")


class DepthClassTests(unittest.TestCase):
    def test_events_are_split_into_seismological_depth_classes(self) -> None:
        result = _provider(
            [
                _event(depth_km=8.0, identifier="shallow"),
                _event(depth_km=150.0, identifier="intermediate"),
                _event(depth_km=520.0, identifier="deep"),
            ]
        ).fetch_bbox(AEGEAN)

        self.assertEqual([f["id"] for f in result.features_by_layer[SHALLOW_LAYER]], ["shallow"])
        self.assertEqual([f["id"] for f in result.features_by_layer[INTERMEDIATE_LAYER]], ["intermediate"])
        self.assertEqual([f["id"] for f in result.features_by_layer[DEEP_LAYER]], ["deep"])

    def test_class_boundaries_fall_on_the_deeper_side(self) -> None:
        result = _provider([_event(depth_km=70.0, identifier="a"), _event(depth_km=300.0, identifier="b")]).fetch_bbox(AEGEAN)
        self.assertEqual(len(result.features_by_layer[INTERMEDIATE_LAYER]), 1)
        self.assertEqual(len(result.features_by_layer[DEEP_LAYER]), 1)
        self.assertEqual(result.features_by_layer[SHALLOW_LAYER], [])

    def test_an_event_without_a_depth_is_treated_as_shallow(self) -> None:
        event = _event()
        event["geometry"]["coordinates"] = [25.0, 37.0]
        result = _provider([event]).fetch_bbox(AEGEAN)
        self.assertEqual(len(result.features_by_layer[SHALLOW_LAYER]), 1)


class SymbolTests(unittest.TestCase):
    """Points cannot be drawn, so every event becomes a magnitude-scaled circle."""

    def _radius(self, feature: dict) -> float:
        ring = feature["geometry"]["coordinates"][0]
        lats = [point[1] for point in ring]
        return (max(lats) - min(lats)) / 2.0

    def test_events_are_closed_polygons(self) -> None:
        feature = _provider([_event()]).fetch_bbox(AEGEAN).features_by_layer[SHALLOW_LAYER][0]
        ring = feature["geometry"]["coordinates"][0]
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(ring[0], ring[-1])
        self.assertGreater(len(ring), 12)

    def test_a_bigger_quake_draws_a_bigger_circle(self) -> None:
        result = _provider([_event(magnitude=3.0, identifier="small"), _event(magnitude=6.0, identifier="big")]).fetch_bbox(AEGEAN)
        by_id = {f["id"]: f for f in result.features_by_layer[SHALLOW_LAYER]}
        self.assertGreater(self._radius(by_id["big"]), self._radius(by_id["small"]) * 2)

    def test_symbols_scale_with_the_window(self) -> None:
        """A radius fixed in degrees would vanish on a city map and swamp a world one."""
        wide = _provider([_event()]).fetch_bbox(AEGEAN)
        narrow = _provider([_event()]).fetch_bbox(BBoxQuery(24.9, 36.9, 25.1, 37.1))
        self.assertGreater(
            self._radius(wide.features_by_layer[SHALLOW_LAYER][0]),
            self._radius(narrow.features_by_layer[SHALLOW_LAYER][0]),
        )

    def test_circles_are_round_on_the_map_not_in_degrees(self) -> None:
        """A degree of longitude is shorter than one of latitude away from the equator."""
        feature = _provider([_event(lat=60.0)]).fetch_bbox(BBoxQuery(20.0, 55.0, 29.0, 65.0)).features_by_layer[SHALLOW_LAYER][0]
        ring = feature["geometry"]["coordinates"][0]
        lon_radius = (max(point[0] for point in ring) - min(point[0] for point in ring)) / 2.0
        lat_radius = (max(point[1] for point in ring) - min(point[1] for point in ring)) / 2.0
        # Corrected for latitude, the longitude radius is wider in degrees.
        self.assertAlmostEqual(lon_radius * math.cos(math.radians(60.0)), lat_radius, places=4)

    def test_huge_events_are_capped(self) -> None:
        settings = SeismicitySettings(max_radius_fraction=0.02)
        feature = _provider([_event(magnitude=9.1)], settings).fetch_bbox(AEGEAN).features_by_layer[SHALLOW_LAYER][0]
        self.assertLessEqual(self._radius(feature), 7.0 * 0.02 + 1e-9)


class PropertyTests(unittest.TestCase):
    def test_events_carry_magnitude_depth_place_and_time(self) -> None:
        feature = _provider([_event()]).fetch_bbox(AEGEAN).features_by_layer[SHALLOW_LAYER][0]
        properties = feature["properties"]
        self.assertEqual(properties["magnitude"], 5.4)
        self.assertEqual(properties["depth_km"], 10.0)
        self.assertEqual(properties["place"], "12 km SW of Nowhere")
        self.assertTrue(properties["event_time"].startswith("20"))
        self.assertEqual(properties["hipparchus_source"], "usgs_earthquakes")

    def test_only_notable_events_are_named(self) -> None:
        result = _provider(
            [_event(magnitude=2.7, identifier="small"), _event(magnitude=5.4, identifier="big")],
            SeismicitySettings(label_min_magnitude=4.0),
        ).fetch_bbox(AEGEAN)
        by_id = {f["id"]: f for f in result.features_by_layer[SHALLOW_LAYER]}
        self.assertEqual(by_id["small"]["properties"]["name"], "")
        self.assertEqual(by_id["big"]["properties"]["name"], "M 5.4")

    def test_metadata_summarises_the_catalogue_window(self) -> None:
        metadata = _provider([_event(magnitude=6.2)], SeismicitySettings(days=30, min_magnitude=4.0)).fetch_bbox(AEGEAN).metadata
        self.assertEqual(metadata["source"], "usgs_earthquakes")
        self.assertEqual(metadata["event_count"], 1)
        self.assertEqual(metadata["strongest_magnitude"], 6.2)
        self.assertEqual(metadata["window_days"], 30)
        self.assertFalse(metadata["truncated"])

    def test_hitting_the_limit_is_reported(self) -> None:
        events = [_event(identifier=f"e{index}") for index in range(3)]
        metadata = _provider(events, SeismicitySettings(limit=3)).fetch_bbox(AEGEAN).metadata
        self.assertTrue(metadata["truncated"])


class MalformedEventTests(unittest.TestCase):
    def test_events_without_a_magnitude_are_skipped(self) -> None:
        result = _provider([_event(magnitude=None), _event(identifier="good")]).fetch_bbox(AEGEAN)
        self.assertEqual([f["id"] for f in result.features_by_layer[SHALLOW_LAYER]], ["good"])

    def test_events_without_coordinates_are_skipped(self) -> None:
        broken = _event()
        broken["geometry"] = {"type": "Point", "coordinates": []}
        result = _provider([broken]).fetch_bbox(AEGEAN)
        self.assertEqual(result.metadata["event_count"], 0)

    def test_an_empty_catalogue_is_not_an_error(self) -> None:
        result = _provider([]).fetch_bbox(AEGEAN)
        self.assertEqual(result.metadata["event_count"], 0)
        self.assertEqual(result.features_by_layer[SHALLOW_LAYER], [])


class ManagerIntegrationTests(unittest.TestCase):
    def test_the_seismicity_model_is_registered_and_fetchable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            manager._optional_providers["usgs_earthquakes"] = _provider([_event()])
            result = manager.fetch_map_model(AEGEAN, "seismicity")

        self.assertEqual(result.metadata["model"], "seismicity")
        self.assertEqual(result.metadata["source"], "usgs_earthquakes")
        self.assertEqual(len(result.features_by_layer[SHALLOW_LAYER]), 1)

    def test_provider_status_is_listed_for_the_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            self.assertTrue(manager.get_provider_statuses()["usgs_earthquakes"].available)


if __name__ == "__main__":
    unittest.main()
