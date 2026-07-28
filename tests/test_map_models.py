from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.map_models import MapModelRegistry
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.simulated_field import TerrainFieldSettings


class MapModelTests(unittest.TestCase):
    def test_default_registry_keeps_osm_live_available(self) -> None:
        registry = MapModelRegistry()
        osm_live = registry.get("osm_live")
        statuses = registry.statuses()

        self.assertEqual(osm_live.provider_ids, ("overpass",))
        self.assertTrue(statuses["overpass"].available)
        self.assertIn("terrain_dem", statuses)

    def test_manager_fetches_optional_geojson_model(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [0.5, 0.5]]},
                    "properties": {"hipparchus_layer": "roads", "name": "Fixture Road"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiles.geojson"
            path.write_text(json.dumps(payload), encoding="utf-8")
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp), vector_tiles_path=path))

            result = manager.fetch_map_model(BBoxQuery(0.0, 0.0, 1.0, 1.0, layers=("roads",)), "vector_tiles")

        self.assertEqual(result.metadata["model"], "vector_tiles")
        self.assertEqual(result.metadata["source"], "vector_tiles")
        self.assertEqual(len(result.features_by_layer["roads"]), 1)



class SimulatedTerrainModelTests(unittest.TestCase):
    """The generated-field model must be selectable with no configuration."""

    def test_model_is_registered_and_labelled_as_synthetic(self) -> None:
        model = MapModelRegistry().get("simulated_terrain")
        self.assertEqual(model.model_id, "simulated_terrain")
        self.assertIn("synthetic", model.label.lower())
        self.assertEqual(model.provider_ids, ("simulated_terrain",))

    def test_registry_status_is_available_without_a_dependency(self) -> None:
        status = MapModelRegistry().statuses()["simulated_terrain"]
        self.assertTrue(status.available)
        self.assertFalse(status.required)

    def test_manager_fetches_the_model_with_no_paths_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            result = manager.fetch_map_model(
                BBoxQuery(23.70, 37.95, 23.80, 38.02, layers=("terrain_contours",)),
                "simulated_terrain",
            )

        self.assertEqual(result.metadata["model"], "simulated_terrain")
        self.assertEqual(result.metadata["source"], "simulated_terrain")
        # No silent fall back to Overpass: this model always produces its own data.
        self.assertNotIn("fallback", result.metadata)
        self.assertTrue(result.features_by_layer["terrain_contours"])
        self.assertTrue(result.features_by_layer["terrain_index_contours"])

    def test_manager_reports_the_provider_as_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            status = manager.get_provider_statuses()["simulated_terrain"]
        self.assertTrue(status.available)

    def test_seed_comes_from_the_launch_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(
                config=DataSourceConfig(
                    local_cache_dir=Path(tmp),
                    simulated_terrain_settings=TerrainFieldSettings(seed=99, grid_size=64),
                )
            )
            result = manager.fetch_map_model(
                BBoxQuery(23.70, 37.95, 23.80, 38.02),
                "simulated_terrain",
            )
        self.assertEqual(result.metadata["provider_metadata"]["simulated_terrain"]["seed"], 99)

    def test_merged_metadata_keeps_the_synthetic_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = DataSourceManager(config=DataSourceConfig(local_cache_dir=Path(tmp)))
            result = manager.fetch_map_model(
                BBoxQuery(23.70, 37.95, 23.80, 38.02),
                "simulated_terrain",
            )
        self.assertTrue(result.metadata["synthetic"])
        self.assertIn("contour_interval_metres", result.metadata["provider_metadata"]["simulated_terrain"])

if __name__ == "__main__":
    unittest.main()
