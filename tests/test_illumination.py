"""Illuminated contours: stroke weight varying along a line to read as depth."""

from __future__ import annotations

import math
import unittest

import numpy as np
from shapely.geometry import LineString, Point

from hipparchus.geometry.contours import orient_uphill_left
from hipparchus.geometry.illumination import (
    IlluminationProfile,
    illuminate_geometries,
)


class OrientationTests(unittest.TestCase):
    """Winding order is the only channel a bare LineString has for slope aspect."""

    @staticmethod
    def _ramp_east(x: float, _y: float) -> float:
        """Ground rising towards +x."""
        return x

    def test_a_line_is_wound_with_high_ground_on_its_left(self) -> None:
        # Contour of the east-rising ramp at x=5: a vertical line. High ground
        # is to the east, so travel must be southward for it to be on the left.
        line = [(5.0, 10.0), (5.0, 0.0)]
        oriented = orient_uphill_left(line, sample=self._ramp_east, level=5.0, probe=0.5)
        self.assertEqual(oriented[0][1], 10.0)
        self.assertEqual(oriented[-1][1], 0.0)

    def test_a_backwards_line_is_reversed(self) -> None:
        line = [(5.0, 0.0), (5.0, 10.0)]
        oriented = orient_uphill_left(line, sample=self._ramp_east, level=5.0, probe=0.5)
        self.assertEqual(oriented[0][1], 10.0)

    def test_orientation_is_idempotent(self) -> None:
        line = [(5.0, 0.0), (5.0, 10.0)]
        once = orient_uphill_left(line, sample=self._ramp_east, level=5.0, probe=0.5)
        twice = orient_uphill_left(once, sample=self._ramp_east, level=5.0, probe=0.5)
        self.assertEqual(once, twice)

    def test_degenerate_input_is_returned_unchanged(self) -> None:
        self.assertEqual(orient_uphill_left([], sample=self._ramp_east, level=0.0, probe=0.5), [])
        single = [(1.0, 1.0)]
        self.assertEqual(orient_uphill_left(single, sample=self._ramp_east, level=0.0, probe=0.5), single)
        repeated = [(1.0, 1.0), (1.0, 1.0)]
        self.assertEqual(orient_uphill_left(repeated, sample=self._ramp_east, level=0.0, probe=0.5), repeated)


class WeightTests(unittest.TestCase):
    def test_shadowed_slopes_draw_heavier_than_lit_ones(self) -> None:
        profile = IlluminationProfile(azimuth_deg=315.0, bands=5, lit_scale=0.4, shadow_scale=1.9)
        self.assertAlmostEqual(profile.weight_for(1.0), 0.4)
        self.assertAlmostEqual(profile.weight_for(-1.0), 1.9)
        self.assertGreater(profile.weight_for(-0.5), profile.weight_for(0.5))

    def test_weights_are_quantised_into_bands(self) -> None:
        profile = IlluminationProfile(bands=3, lit_scale=1.0, shadow_scale=2.0)
        weights = {profile.weight_for(value) for value in np.linspace(-1.0, 1.0, 50)}
        self.assertEqual(len(weights), 3)

    def test_a_single_band_gives_one_uniform_weight(self) -> None:
        profile = IlluminationProfile(bands=1, lit_scale=0.5, shadow_scale=2.0)
        weights = {profile.weight_for(value) for value in (-1.0, 0.0, 1.0)}
        self.assertEqual(len(weights), 1)


class IlluminateGeometriesTests(unittest.TestCase):
    PROFILE = IlluminationProfile(azimuth_deg=315.0, bands=5, lit_scale=0.4, shadow_scale=1.9)

    def test_geometry_and_weight_lists_stay_parallel(self) -> None:
        ring = LineString([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        chunks, weights = illuminate_geometries([ring], self.PROFILE)
        self.assertEqual(len(chunks), len(weights))
        self.assertTrue(chunks)

    def test_a_closed_ring_is_split_into_lit_and_shadowed_runs(self) -> None:
        """A hill lit from one side must not come out at one uniform weight."""
        ring = LineString([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        _chunks, weights = illuminate_geometries([ring], self.PROFILE)
        self.assertGreater(len(set(weights)), 1)
        self.assertGreater(max(weights), min(weights))

    def test_the_lit_side_is_opposite_the_shadowed_side(self) -> None:
        # Ring wound counter-clockwise: the left of travel points outward, so
        # the north-west arc faces the north-west light.
        radius = 10.0
        coordinates = [
            (radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)))
            for angle in range(0, 361, 10)
        ]
        chunks, weights = illuminate_geometries([LineString(coordinates)], self.PROFILE)

        lightest = chunks[weights.index(min(weights))]
        heaviest = chunks[weights.index(max(weights))]
        light_direction = Point(-radius * 0.7071, radius * 0.7071)
        self.assertLess(
            lightest.distance(light_direction),
            heaviest.distance(light_direction),
            "the thinnest stroke must sit on the side facing the light",
        )

    def test_reversing_a_line_swaps_lit_for_shadowed(self) -> None:
        line = LineString([(0, 0), (10, 0)])
        _forward_chunks, forward = illuminate_geometries([line], self.PROFILE)
        _reverse_chunks, reverse = illuminate_geometries([LineString(list(line.coords)[::-1])], self.PROFILE)
        self.assertNotEqual(forward, reverse)

    def test_chunks_cover_the_whole_line(self) -> None:
        line = LineString([(0, 0), (5, 5), (10, 0), (15, 5)])
        chunks, _weights = illuminate_geometries([line], self.PROFILE)
        self.assertAlmostEqual(sum(chunk.length for chunk in chunks), line.length, places=6)

    def test_runs_are_merged_rather_than_split_per_segment(self) -> None:
        """One chunk per segment would explode the SVG into unusable fragments."""
        straight = LineString([(x, 0.0) for x in range(60)])
        chunks, _weights = illuminate_geometries([straight], self.PROFILE)
        self.assertEqual(len(chunks), 1)

    def test_polygons_and_points_are_ignored(self) -> None:
        chunks, weights = illuminate_geometries([Point(1, 1)], self.PROFILE)
        self.assertEqual(chunks, [])
        self.assertEqual(weights, [])

    def test_empty_input_is_safe(self) -> None:
        self.assertEqual(illuminate_geometries([], self.PROFILE), ([], []))


if __name__ == "__main__":
    unittest.main()
