"""Filled elevation bands: regions nest, and the nesting has to be measured."""

from __future__ import annotations

import unittest

import numpy as np
from shapely.geometry import Point, Polygon

from hipparchus.geometry.bands import (
    band_boundaries,
    elevation_bands,
    map_coordinates,
    region_at_or_above,
)


def _cone(size: int = 61, peak: float = 100.0) -> np.ndarray:
    """A single peak at the centre falling away radially."""
    axis = np.linspace(-1.0, 1.0, size)
    xs, ys = np.meshgrid(axis, axis)
    return np.clip(peak * (1.0 - np.hypot(xs, ys)), 0.0, None)


def _crater(size: int = 81, rim: float = 100.0) -> np.ndarray:
    """A ring-shaped rim with a hollow inside: the case that breaks naive fills."""
    axis = np.linspace(-1.0, 1.0, size)
    xs, ys = np.meshgrid(axis, axis)
    radius = np.hypot(xs, ys)
    # Rises to the rim at r = 0.55, drops away both outside and inside.
    return rim * np.clip(1.0 - np.abs(radius - 0.55) / 0.45, 0.0, None)


class RegionTests(unittest.TestCase):
    def test_a_cone_gives_one_disc_per_level(self) -> None:
        grid = _cone()
        region = region_at_or_above(grid, 50.0)
        self.assertFalse(region.is_empty)
        self.assertTrue(region.is_valid)
        # Half height on a cone is half the radius, so a quarter of the area of
        # the full base disc.
        self.assertAlmostEqual(region.area / region_at_or_above(grid, 0.1).area, 0.25, delta=0.06)

    def test_higher_levels_nest_inside_lower_ones(self) -> None:
        grid = _cone()
        low = region_at_or_above(grid, 20.0)
        high = region_at_or_above(grid, 70.0)
        self.assertLess(high.area, low.area)
        self.assertTrue(low.buffer(0.5).contains(high))

    def test_a_crater_rim_region_has_a_hole(self) -> None:
        """The failure this whole approach exists to avoid: filling the hollow."""
        region = region_at_or_above(_crater(), 60.0)
        self.assertFalse(region.is_empty)
        polygons = list(getattr(region, "geoms", [region]))
        self.assertTrue(
            any(len(polygon.interiors) > 0 for polygon in polygons),
            "a rim enclosing lower ground must produce a hole, not a filled disc",
        )

    def test_the_hollow_inside_a_crater_is_not_covered(self) -> None:
        grid = _crater()
        region = region_at_or_above(grid, 60.0)
        centre = Point((grid.shape[1] - 1) / 2.0, (grid.shape[0] - 1) / 2.0)
        self.assertFalse(region.contains(centre))

    def test_a_field_entirely_above_the_level_fills_the_map(self) -> None:
        grid = np.full((20, 30), 500.0)
        region = region_at_or_above(grid, 100.0)
        self.assertAlmostEqual(region.area, 29.0 * 19.0, places=6)

    def test_a_field_entirely_below_the_level_is_empty(self) -> None:
        self.assertTrue(region_at_or_above(np.full((20, 30), 5.0), 100.0).is_empty)

    def test_a_landform_running_off_the_edge_is_closed_against_the_frame(self) -> None:
        """Without the sentinel border this leaves an open chain and no polygon."""
        grid = np.tile(np.linspace(0.0, 100.0, 40), (30, 1))
        region = region_at_or_above(grid, 50.0)
        self.assertFalse(region.is_empty)
        self.assertTrue(region.is_valid)
        # The eastern half is above 50, so about half the map.
        self.assertAlmostEqual(region.area / (39.0 * 29.0), 0.5, delta=0.05)

    def test_regions_stay_inside_the_grid(self) -> None:
        grid = _cone()
        region = region_at_or_above(grid, 10.0)
        min_x, min_y, max_x, max_y = region.bounds
        self.assertGreaterEqual(min_x, -1e-6)
        self.assertGreaterEqual(min_y, -1e-6)
        self.assertLessEqual(max_x, grid.shape[1] - 1 + 1e-6)
        self.assertLessEqual(max_y, grid.shape[0] - 1 + 1e-6)

    def test_non_finite_samples_are_treated_as_absent(self) -> None:
        grid = _cone()
        grid[0:5, 0:5] = np.nan
        region = region_at_or_above(grid, 10.0)
        self.assertTrue(region.is_valid)

    def test_degenerate_grids_are_safe(self) -> None:
        self.assertTrue(region_at_or_above(np.zeros((1, 5)), 0.5).is_empty)
        self.assertTrue(region_at_or_above(np.full((5, 5), np.nan), 0.5).is_empty)


class BandTests(unittest.TestCase):
    def test_bands_tile_the_ground_without_overlapping(self) -> None:
        grid = _cone()
        bands = elevation_bands(grid, band_boundaries(0.0, 100.0, 8))
        self.assertGreater(len(bands), 4)
        for first in range(len(bands)):
            for second in range(first + 1, len(bands)):
                overlap = bands[first].geometry.intersection(bands[second].geometry).area
                self.assertLess(overlap, 0.5, "bands must not overlap")

    def test_bands_cover_the_ground_they_describe(self) -> None:
        grid = _cone()
        bands = elevation_bands(grid, band_boundaries(0.0, 100.0, 8))
        total = sum(band.geometry.area for band in bands)
        base = region_at_or_above(grid, 0.0).area
        self.assertAlmostEqual(total / base, 1.0, delta=0.05)

    def test_each_band_sits_between_its_own_bounds(self) -> None:
        bands = elevation_bands(_cone(), band_boundaries(0.0, 100.0, 5))
        for band in bands:
            self.assertLess(band.lower, band.upper)
            self.assertGreater(band.midpoint, band.lower)
            self.assertLess(band.midpoint, band.upper)

    def test_bands_are_returned_low_to_high(self) -> None:
        bands = elevation_bands(_cone(), band_boundaries(0.0, 100.0, 6))
        self.assertEqual([band.lower for band in bands], sorted(band.lower for band in bands))

    def test_a_band_over_a_crater_keeps_its_hole(self) -> None:
        bands = elevation_bands(_crater(), band_boundaries(0.0, 100.0, 5))
        self.assertTrue(bands)
        has_hole = any(
            any(polygon.interiors for polygon in getattr(band.geometry, "geoms", [band.geometry]))
            for band in bands
        )
        self.assertTrue(has_hole, "a ring-shaped landform must yield a banded ring")

    def test_every_band_is_valid_geometry(self) -> None:
        for band in elevation_bands(_cone(), band_boundaries(0.0, 100.0, 10)):
            self.assertTrue(band.geometry.is_valid)
            self.assertFalse(band.geometry.is_empty)

    def test_too_few_boundaries_yield_nothing(self) -> None:
        self.assertEqual(elevation_bands(_cone(), [50.0]), [])
        self.assertEqual(elevation_bands(_cone(), []), [])

    def test_duplicate_boundaries_are_collapsed(self) -> None:
        bands = elevation_bands(_cone(), [0.0, 50.0, 50.0, 100.0])
        self.assertEqual(len(bands), 2)


class BoundaryTests(unittest.TestCase):
    def test_boundaries_span_the_range(self) -> None:
        self.assertEqual(band_boundaries(0.0, 100.0, 4), [0.0, 25.0, 50.0, 75.0, 100.0])

    def test_degenerate_ranges_yield_nothing(self) -> None:
        self.assertEqual(band_boundaries(50.0, 50.0, 4), [])
        self.assertEqual(band_boundaries(100.0, 0.0, 4), [])
        self.assertEqual(band_boundaries(0.0, 100.0, 0), [])


class CoordinateMappingTests(unittest.TestCase):
    def test_index_space_polygons_are_remapped_with_holes_intact(self) -> None:
        polygon = Polygon(
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            [[(3, 3), (6, 3), (6, 6), (3, 6)]],
        )

        def mapper(row: float, col: float) -> tuple[float, float]:
            return (col * 0.1, 50.0 - row * 0.1)

        mapped = map_coordinates(polygon, mapper)
        self.assertEqual(len(mapped.interiors), 1)
        self.assertAlmostEqual(mapped.exterior.coords[0][0], 0.0)
        self.assertAlmostEqual(mapped.exterior.coords[0][1], 50.0)
        # The mapper reads (row, col) while shapely holds (x=col, y=row).
        self.assertAlmostEqual(mapped.bounds[2], 1.0)


if __name__ == "__main__":
    unittest.main()
