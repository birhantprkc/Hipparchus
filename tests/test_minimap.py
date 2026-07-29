"""The locator: where the area is, at a glance."""

from __future__ import annotations

import unittest

from hipparchus.ui.minimap import MAX_LATITUDE, describe, geometry, project


class ProjectionTests(unittest.TestCase):
    def test_the_world_fills_the_widget(self) -> None:
        self.assertEqual(project(-180.0, MAX_LATITUDE, 200, 100), (0.0, 0.0))
        self.assertEqual(project(180.0, -MAX_LATITUDE, 200, 100), (200.0, 100.0))

    def test_the_origin_is_the_centre(self) -> None:
        x, y = project(0.0, 0.0, 200, 100)
        self.assertAlmostEqual(x, 100.0)
        self.assertAlmostEqual(y, 50.0)

    def test_north_is_up(self) -> None:
        self.assertLess(project(0.0, 60.0, 200, 100)[1], project(0.0, -60.0, 200, 100)[1])

    def test_polar_latitudes_are_clamped_not_wrapped(self) -> None:
        self.assertEqual(project(0.0, 89.9, 200, 100)[1], project(0.0, MAX_LATITUDE, 200, 100)[1])


class GeometryTests(unittest.TestCase):
    ATHENS = (23.57, 37.81, 23.89, 38.13)

    def test_the_area_box_sits_where_the_area_is(self) -> None:
        left, top, right, bottom = geometry(self.ATHENS, 240, 120).box
        # East of Greenwich and north of the equator.
        self.assertGreater(left, 120.0)
        self.assertLess(top, 60.0)
        self.assertGreaterEqual(right, left)
        self.assertGreaterEqual(bottom, top)

    def test_a_city_area_is_marked_because_it_is_a_speck(self) -> None:
        result = geometry(self.ATHENS, 240, 120)
        self.assertTrue(result.is_speck)
        self.assertIsNotNone(result.marker)

    def test_a_continental_area_needs_no_marker(self) -> None:
        result = geometry((-20.0, 30.0, 40.0, 70.0), 240, 120)
        self.assertFalse(result.is_speck)
        self.assertIsNone(result.marker)

    def test_a_tiny_area_never_collapses_to_nothing(self) -> None:
        left, top, right, bottom = geometry((23.75, 37.97, 23.7501, 37.9701), 240, 120).box
        self.assertGreaterEqual(right - left, 1.0)
        self.assertGreaterEqual(bottom - top, 1.0)

    def test_reversed_bounds_are_tolerated(self) -> None:
        forward = geometry((10.0, 40.0, 20.0, 50.0), 240, 120).box
        reversed_ = geometry((20.0, 50.0, 10.0, 40.0), 240, 120).box
        self.assertEqual(forward, reversed_)

    def test_the_graticule_stays_inside_the_widget(self) -> None:
        result = geometry(self.ATHENS, 240, 120)
        self.assertTrue(all(0.0 <= x <= 240.0 for x in result.meridians))
        self.assertTrue(all(0.0 <= y <= 120.0 for y in result.parallels))
        self.assertTrue(result.meridians and result.parallels)


class DescribeTests(unittest.TestCase):
    def test_it_names_the_hemisphere_and_the_span(self) -> None:
        self.assertEqual(
            describe((23.57, 37.81, 23.89, 38.13)),
            "37.97° N  23.73° E   ·   0.32° × 0.32°",
        )

    def test_southern_and_western_places_read_correctly(self) -> None:
        text = describe((-58.5, -34.7, -58.3, -34.5))
        self.assertIn("S", text)
        self.assertIn("W", text)


if __name__ == "__main__":
    unittest.main()
