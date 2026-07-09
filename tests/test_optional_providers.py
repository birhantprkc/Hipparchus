from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hipparchus.data_sources.optional_providers import natural_earth_provider
from hipparchus.data_sources.optional_providers import _contour_levels, _lonlat_to_tile, _tile_point_to_lonlat
from hipparchus.data_sources.provider import BBoxQuery


class OptionalProviderTests(unittest.TestCase):
    def test_geojson_source_normalizes_to_feature_collection(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.1]]],
                    },
                    "properties": {"hipparchus_layer": "water", "name": "Test Water"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [4.0, 4.0]},
                    "properties": {"hipparchus_layer": "places", "name": "Outside"},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.geojson"
            path.write_text(json.dumps(payload), encoding="utf-8")
            provider = natural_earth_provider(path)

            result = provider.fetch_bbox(BBoxQuery(0.0, 0.0, 1.0, 1.0, layers=("water", "places")))

        self.assertEqual(result.metadata["source"], "natural_earth")
        self.assertEqual(len(result.features_by_layer["water"]), 1)
        self.assertEqual(len(result.features_by_layer["places"]), 0)

    def test_tile_coordinate_helpers_roundtrip_center(self) -> None:
        zoom = 4
        x, y = _lonlat_to_tile(0.0, 0.0, zoom)
        lon, lat = _tile_point_to_lonlat(zoom, x, y, 2048.0, 2048.0, 4096.0)

        self.assertLess(abs(lon), 12.0)
        self.assertLess(abs(lat), 12.0)

    def test_contour_levels_are_inside_range(self) -> None:
        levels = _contour_levels(100.0, 220.0, count=3)

        self.assertEqual(len(levels), 3)
        self.assertTrue(all(100.0 < level < 220.0 for level in levels))


if __name__ == "__main__":
    unittest.main()
