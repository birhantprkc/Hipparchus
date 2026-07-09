from __future__ import annotations

import unittest

from shapely.geometry import LineString

from hipparchus.geometry.projection import ProjectionProfile


class ProjectionTests(unittest.TestCase):
    def test_web_mercator_roundtrip_point(self) -> None:
        profile = ProjectionProfile.from_bbox((23.7, 37.9, 23.8, 38.0), mode="web_mercator")
        x, y = profile.project_point(23.75, 37.95)
        lon, lat = profile.unproject_point(x, y)

        self.assertAlmostEqual(lon, 23.75, places=6)
        self.assertAlmostEqual(lat, 37.95, places=6)

    def test_local_projection_centers_aoi(self) -> None:
        profile = ProjectionProfile.from_bbox((10.0, 20.0, 12.0, 22.0), mode="local_azimuthal")
        x, y = profile.project_point(11.0, 21.0)

        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_project_geometry_changes_coordinate_scale(self) -> None:
        profile = ProjectionProfile.from_bbox((0.0, 0.0, 1.0, 1.0), mode="web_mercator")
        projected = profile.project_geometry(LineString([(0.0, 0.0), (1.0, 1.0)]))

        self.assertGreater(projected.length, 100000.0)


if __name__ == "__main__":
    unittest.main()
