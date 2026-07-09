from __future__ import annotations

import unittest

from shapely.geometry import LineString, Polygon

from hipparchus.geometry.smoothing import smooth_layer_geometries


class SmoothingTests(unittest.TestCase):
    def test_smooths_roads_deterministically(self) -> None:
        line = LineString([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
        smoothed, count, invalid = smooth_layer_geometries("roads_residential", [line], 1)

        self.assertEqual(count, 1)
        self.assertEqual(invalid, 0)
        self.assertGreater(len(smoothed[0].coords), len(line.coords))
        self.assertEqual(list(smoothed[0].coords), list(smooth_layer_geometries("roads_residential", [line], 1)[0][0].coords))

    def test_does_not_smooth_buildings(self) -> None:
        building = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
        smoothed, count, invalid = smooth_layer_geometries("buildings", [building], 3)

        self.assertEqual(count, 0)
        self.assertEqual(invalid, 0)
        self.assertEqual(len(smoothed[0].exterior.coords), len(building.exterior.coords))

    def test_smooths_water_polygon_boundaries(self) -> None:
        water = Polygon([(0, 0), (2, 0), (2, 1), (1, 2), (0, 0)])
        smoothed, count, invalid = smooth_layer_geometries("water", [water], 1)

        self.assertEqual(count, 1)
        self.assertEqual(invalid, 0)
        self.assertGreater(len(smoothed[0].exterior.coords), len(water.exterior.coords))


if __name__ == "__main__":
    unittest.main()
