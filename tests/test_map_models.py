from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.map_models import MapModelRegistry
from hipparchus.data_sources.provider import BBoxQuery


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


if __name__ == "__main__":
    unittest.main()
