"""Tests for the pure-numpy marching-squares contouring module."""

from __future__ import annotations

import math
import unittest

import numpy as np

from hipparchus.geometry.contours import (
    ContourLevels,
    contour_levels,
    contour_polylines,
    polyline_to_lonlat,
)


class ContourLevelTests(unittest.TestCase):
    def test_levels_land_on_interval_multiples(self) -> None:
        levels = contour_levels(3.0, 47.0, interval=10.0, index_every=5)
        self.assertEqual(levels.all_levels, (10.0, 20.0, 30.0, 40.0))

    def test_index_levels_are_every_nth_interval(self) -> None:
        levels = contour_levels(0.0, 260.0, interval=25.0, index_every=4)
        # index spacing is interval * index_every = 100
        self.assertEqual(levels.index, (100.0, 200.0))
        self.assertNotIn(100.0, levels.minor)
        self.assertEqual(len(levels.minor) + len(levels.index), len(levels.all_levels))

    def test_minor_and_index_are_disjoint_and_sorted(self) -> None:
        levels = contour_levels(-120.0, 340.0, interval=20.0, index_every=5)
        self.assertEqual(sorted(levels.all_levels), list(levels.all_levels))
        self.assertFalse(set(levels.minor) & set(levels.index))

    def test_no_index_lines_when_accenting_is_switched_off(self) -> None:
        """A dense sheet reads depth from line density; an accent interrupts it."""
        levels = contour_levels(0.0, 100.0, interval=10.0, index_every=0)
        self.assertEqual(levels.index, ())
        self.assertEqual(len(levels.minor), 9)
        self.assertEqual(len(levels.all_levels), 9)

    def test_negative_accent_spacing_is_treated_as_off(self) -> None:
        self.assertEqual(contour_levels(0.0, 100.0, interval=10.0, index_every=-3).index, ())

    def test_empty_when_range_is_degenerate(self) -> None:
        self.assertEqual(contour_levels(10.0, 10.0, interval=5.0).all_levels, ())
        self.assertEqual(contour_levels(50.0, 10.0, interval=5.0).all_levels, ())

    def test_non_positive_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            contour_levels(0.0, 100.0, interval=0.0)

    def test_level_count_is_capped(self) -> None:
        levels = contour_levels(0.0, 1_000_000.0, interval=1.0, max_levels=64)
        self.assertLessEqual(len(levels.all_levels), 64)

    def test_levels_type(self) -> None:
        self.assertIsInstance(contour_levels(0.0, 10.0, interval=2.0), ContourLevels)


class ContourPolylineTests(unittest.TestCase):
    def test_planar_ramp_yields_one_straight_line(self) -> None:
        # f(row, col) = col, so the level 3.5 contour is the vertical line col=3.5
        grid = np.tile(np.arange(8, dtype=float), (6, 1))
        lines = contour_polylines(grid, 3.5)
        self.assertEqual(len(lines), 1)
        cols = [col for _row, col in lines[0]]
        for col in cols:
            self.assertAlmostEqual(col, 3.5, places=9)
        # spans the full grid height
        rows = sorted(row for row, _col in lines[0])
        self.assertAlmostEqual(rows[0], 0.0)
        self.assertAlmostEqual(rows[-1], 5.0)

    def test_cone_yields_a_closed_ring(self) -> None:
        size = 41
        axis = np.linspace(-10.0, 10.0, size)
        xs, ys = np.meshgrid(axis, axis)
        grid = 10.0 - np.hypot(xs, ys)
        lines = contour_polylines(grid, 5.0)
        self.assertEqual(len(lines), 1)
        ring = lines[0]
        self.assertGreater(len(ring), 8)
        self.assertEqual(ring[0], ring[-1], "a closed contour must repeat its first point")

        # every point sits on the radius-5 circle, in grid index units
        centre = (size - 1) / 2.0
        scale = 20.0 / (size - 1)
        for row, col in ring:
            radius = math.hypot((col - centre) * scale, (row - centre) * scale)
            self.assertAlmostEqual(radius, 5.0, delta=0.15)

    def test_polyline_points_are_connected(self) -> None:
        axis = np.linspace(-3.0, 3.0, 30)
        xs, ys = np.meshgrid(axis, axis)
        grid = np.sin(xs) * np.cos(ys)
        for line in contour_polylines(grid, 0.25):
            for (r0, c0), (r1, c1) in zip(line, line[1:]):
                # consecutive crossings always sit on edges of one shared cell
                self.assertLessEqual(math.hypot(r1 - r0, c1 - c0), math.sqrt(2.0) + 1e-9)

    def test_level_above_and_below_data_yields_nothing(self) -> None:
        grid = np.tile(np.arange(8, dtype=float), (6, 1))
        self.assertEqual(contour_polylines(grid, -5.0), [])
        self.assertEqual(contour_polylines(grid, 99.0), [])

    def test_flat_field_at_exactly_the_level_yields_nothing(self) -> None:
        grid = np.full((6, 6), 3.0)
        self.assertEqual(contour_polylines(grid, 3.0), [])

    def test_two_separate_peaks_yield_two_rings(self) -> None:
        axis = np.linspace(-1.0, 1.0, 60)
        xs, ys = np.meshgrid(axis, axis)
        left = np.exp(-(((xs + 0.5) * 6) ** 2 + (ys * 6) ** 2))
        right = np.exp(-(((xs - 0.5) * 6) ** 2 + (ys * 6) ** 2))
        lines = contour_polylines(left + right, 0.5)
        self.assertEqual(len(lines), 2)
        for ring in lines:
            self.assertEqual(ring[0], ring[-1])

    def test_saddle_cell_is_resolved_without_dangling_edges(self) -> None:
        # classic saddle: opposite corners high, the other two low
        grid = np.array(
            [
                [2.0, 0.0, 2.0],
                [0.0, 1.0, 0.0],
                [2.0, 0.0, 2.0],
            ]
        )
        lines = contour_polylines(grid, 1.0)
        self.assertTrue(lines)
        for line in lines:
            self.assertGreaterEqual(len(line), 2)

    def test_degenerate_grids_are_safe(self) -> None:
        self.assertEqual(contour_polylines(np.zeros((1, 5)), 0.5), [])
        self.assertEqual(contour_polylines(np.zeros((5, 1)), 0.5), [])
        self.assertEqual(contour_polylines(np.zeros((0, 0)), 0.5), [])

    def test_nan_holes_do_not_crash(self) -> None:
        grid = np.tile(np.arange(8, dtype=float), (6, 1))
        grid[2, 2] = np.nan
        lines = contour_polylines(grid, 3.5)
        for line in lines:
            for row, col in line:
                self.assertTrue(math.isfinite(row) and math.isfinite(col))

    def test_result_is_deterministic(self) -> None:
        axis = np.linspace(-3.0, 3.0, 24)
        xs, ys = np.meshgrid(axis, axis)
        grid = np.sin(xs) * np.cos(ys)
        self.assertEqual(contour_polylines(grid, 0.1), contour_polylines(grid, 0.1))


class PolylineProjectionTests(unittest.TestCase):
    def test_index_space_maps_onto_the_bbox_corners(self) -> None:
        bounds = (10.0, 40.0, 12.0, 41.0)  # min_lon, min_lat, max_lon, max_lat
        shape = (5, 9)
        line = [(0.0, 0.0), (4.0, 8.0)]
        projected = polyline_to_lonlat(line, bounds=bounds, shape=shape)
        # row 0 is the north edge, the last row the south edge
        self.assertAlmostEqual(projected[0][0], 10.0)
        self.assertAlmostEqual(projected[0][1], 41.0)
        self.assertAlmostEqual(projected[1][0], 12.0)
        self.assertAlmostEqual(projected[1][1], 40.0)

    def test_fractional_indices_interpolate(self) -> None:
        bounds = (0.0, 0.0, 4.0, 2.0)
        projected = polyline_to_lonlat([(1.0, 2.0)], bounds=bounds, shape=(3, 5))
        self.assertAlmostEqual(projected[0][0], 2.0)
        self.assertAlmostEqual(projected[0][1], 1.0)


if __name__ == "__main__":
    unittest.main()
