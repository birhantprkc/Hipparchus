"""Tests for the simulated (synthetic) terrain field provider."""

from __future__ import annotations

from pathlib import Path
import unittest

import numpy as np

from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.simulated_field import (
    TerrainFieldSettings,
    elevation_grid,
    field_wavelength_deg,
    nice_interval,
    relief_metres_for_window,
    resolvable_octaves,
    simulated_terrain_provider,
)


ATHENS = BBoxQuery(min_lon=23.70, min_lat=37.95, max_lon=23.80, max_lat=38.02)


class NiceIntervalTests(unittest.TestCase):
    def test_interval_is_a_round_number(self) -> None:
        for value_range in (7.0, 83.0, 940.0, 12_500.0, 0.42):
            interval = nice_interval(value_range, target_lines=40)
            mantissa = interval / (10 ** np.floor(np.log10(interval)))
            self.assertAlmostEqual(min([1.0, 2.0, 5.0], key=lambda m: abs(m - mantissa)), mantissa, places=9)

    def test_interval_gives_roughly_the_requested_line_count(self) -> None:
        interval = nice_interval(1000.0, target_lines=40)
        self.assertGreaterEqual(1000.0 / interval, 20.0)
        self.assertLessEqual(1000.0 / interval, 80.0)

    def test_degenerate_range_is_safe(self) -> None:
        self.assertGreater(nice_interval(0.0, target_lines=40), 0.0)
        self.assertGreater(nice_interval(-5.0, target_lines=40), 0.0)


class LandformScaleTests(unittest.TestCase):
    """One fixed landform size cannot serve AOIs spanning two orders of magnitude.

    Too large for the window and every contour is one flank of one hill -- the
    parallel 'wood grain' failure. Too small and a wide window silts up. The
    landform size therefore follows the window.
    """

    LONDON = (-0.15, 51.48, -0.02, 51.56)
    CITY = (23.68, 37.94, 23.80, 38.03)
    WIDE = (23.4, 37.7, 24.0, 38.2)
    DEEP = (23.740, 37.975, 23.752, 37.983)

    def test_the_window_holds_one_or_two_landforms_at_every_zoom(self) -> None:
        for name, bounds in (("london", self.LONDON), ("city", self.CITY), ("wide", self.WIDE), ("deep", self.DEEP)):
            with self.subTest(aoi=name):
                span = min(
                    abs(bounds[2] - bounds[0]) * np.cos(np.radians((bounds[1] + bounds[3]) / 2)),
                    abs(bounds[3] - bounds[1]),
                )
                ratio = field_wavelength_deg(bounds) / span
                self.assertGreater(ratio, 0.55)
                self.assertLess(ratio, 2.5)

    def test_wavelength_does_not_depend_on_where_the_window_is(self) -> None:
        """Panning must not rescale the landscape, or panning is useless."""
        west = field_wavelength_deg((10.0, 40.0, 10.5, 40.4))
        east = field_wavelength_deg((17.3, 40.0, 17.8, 40.4))
        south = field_wavelength_deg((10.0, 12.0, 10.5, 12.4))
        self.assertEqual(west, east)
        self.assertEqual(west, south)

    def test_small_changes_in_window_size_land_on_the_same_rung(self) -> None:
        base = field_wavelength_deg((0.0, 40.0, 0.40, 40.30))
        nudged = field_wavelength_deg((0.0, 40.0, 0.43, 40.32))
        self.assertEqual(base, nudged)

    def test_zooming_far_enough_changes_rung_by_powers_of_two(self) -> None:
        wide = field_wavelength_deg((0.0, 40.0, 0.80, 40.80))
        tight = field_wavelength_deg((0.0, 40.0, 0.10, 40.10))
        self.assertAlmostEqual(wide / tight, 8.0, places=6)

    def test_relief_follows_landform_size(self) -> None:
        """A kilometre of relief in a kilometre-wide window would be a cliff."""
        wide = relief_metres_for_window(self.WIDE)
        deep = relief_metres_for_window(self.DEEP)
        self.assertGreater(wide, deep * 10)
        self.assertLess(deep, 250.0)

    def test_a_coarser_grid_drops_detail_it_cannot_draw(self) -> None:
        coarse = resolvable_octaves(self.WIDE, settings=TerrainFieldSettings(grid_size=64))
        fine = resolvable_octaves(self.WIDE, settings=TerrainFieldSettings(grid_size=512))
        self.assertLess(coarse, fine)

    def test_detail_no_longer_depends_on_how_far_you_zoomed(self) -> None:
        """With the landform following the window, every zoom carries the same structure."""
        self.assertEqual(resolvable_octaves(self.WIDE), resolvable_octaves(self.DEEP))

    def test_every_zoom_keeps_enough_octaves_to_read_as_terrain(self) -> None:
        for name, bounds in (("london", self.LONDON), ("city", self.CITY), ("wide", self.WIDE), ("deep", self.DEEP)):
            with self.subTest(aoi=name):
                self.assertGreaterEqual(resolvable_octaves(bounds), 5)

    def test_degenerate_window_falls_back_to_the_anchor(self) -> None:
        self.assertEqual(field_wavelength_deg((5.0, 5.0, 5.0, 5.0)), TerrainFieldSettings().base_wavelength_deg)


class ElevationGridTests(unittest.TestCase):
    def test_grid_shape_and_finiteness(self) -> None:
        settings = TerrainFieldSettings(grid_size=64)
        grid = elevation_grid((23.7, 37.9, 23.9, 38.1), settings=settings)
        self.assertEqual(grid.shape, (64, 64))
        self.assertTrue(np.isfinite(grid).all())

    def test_same_seed_and_bbox_give_an_identical_field(self) -> None:
        settings = TerrainFieldSettings(grid_size=48, seed=11)
        first = elevation_grid((23.7, 37.9, 23.9, 38.1), settings=settings)
        second = elevation_grid((23.7, 37.9, 23.9, 38.1), settings=settings)
        np.testing.assert_array_equal(first, second)

    def test_a_different_seed_gives_a_different_field(self) -> None:
        bounds = (23.7, 37.9, 23.9, 38.1)
        first = elevation_grid(bounds, settings=TerrainFieldSettings(grid_size=48, seed=11))
        second = elevation_grid(bounds, settings=TerrainFieldSettings(grid_size=48, seed=12))
        self.assertFalse(np.allclose(first, second))

    def test_the_field_is_anchored_to_geography_not_to_the_window(self) -> None:
        """Panning must reveal the same landscape, not re-roll a new one."""
        settings = TerrainFieldSettings(grid_size=101, seed=5)
        west = elevation_grid((10.0, 40.0, 11.0, 41.0), settings=settings)
        east = elevation_grid((10.5, 40.0, 11.5, 41.0), settings=settings)
        # Both grids sample a 0.01 deg lattice, so the eastern half of the west
        # window is the western half of the east window.
        np.testing.assert_allclose(west[:, 50:], east[:, :51], atol=1e-6)

    def test_relief_stays_within_the_scale_for_that_window(self) -> None:
        settings = TerrainFieldSettings(grid_size=96, relief_metres=900.0, seed=3)
        bounds = (23.0, 37.0, 24.0, 38.0)
        ceiling = relief_metres_for_window(bounds, settings=settings)
        grid = elevation_grid(bounds, settings=settings)
        self.assertGreaterEqual(grid.min(), -1.0)
        self.assertLessEqual(grid.max(), ceiling + 1.0)

    def test_the_field_has_real_relief(self) -> None:
        settings = TerrainFieldSettings(grid_size=96, seed=3)
        grid = elevation_grid((23.0, 37.0, 24.0, 38.0), settings=settings)
        self.assertGreater(grid.max() - grid.min(), 100.0)


class SimulatedProviderTests(unittest.TestCase):
    def test_provider_is_available_without_any_source_path(self) -> None:
        status = simulated_terrain_provider().status()
        self.assertTrue(status.available)
        self.assertEqual(status.provider_id, "simulated_terrain")

    def test_status_says_the_data_is_synthetic(self) -> None:
        self.assertIn("synthetic", simulated_terrain_provider().status().detail.lower())

    def test_a_source_path_is_accepted_and_ignored(self) -> None:
        provider = simulated_terrain_provider()
        provider.source_path = Path("/nowhere/at/all.tif")
        self.assertTrue(provider.status().available)
        result = provider.fetch_bbox(ATHENS)
        self.assertTrue(result.features_by_layer["terrain_contours"])

    def test_fetch_produces_minor_and_index_contours(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        self.assertTrue(result.features_by_layer["terrain_contours"])
        self.assertTrue(result.features_by_layer["terrain_index_contours"])

    def test_contours_are_linework(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        for feature in result.features_by_layer["terrain_contours"]:
            self.assertEqual(feature["geometry"]["type"], "LineString")
            self.assertGreaterEqual(len(feature["geometry"]["coordinates"]), 2)

    def test_contours_stay_inside_the_requested_bbox(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        for feature in result.features_by_layer["terrain_contours"]:
            for lon, lat in feature["geometry"]["coordinates"]:
                self.assertGreaterEqual(lon, ATHENS.min_lon - 1e-6)
                self.assertLessEqual(lon, ATHENS.max_lon + 1e-6)
                self.assertGreaterEqual(lat, ATHENS.min_lat - 1e-6)
                self.assertLessEqual(lat, ATHENS.max_lat + 1e-6)

    def test_elevations_sit_on_the_contour_interval(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        interval = float(result.metadata["contour_interval_metres"])
        index_every = int(result.metadata["index_every"])
        for feature in result.features_by_layer["terrain_contours"]:
            self.assertAlmostEqual(float(feature["properties"]["elevation"]) % interval, 0.0, places=6)
        for feature in result.features_by_layer["terrain_index_contours"]:
            elevation = float(feature["properties"]["elevation"])
            self.assertAlmostEqual(elevation % (interval * index_every), 0.0, places=6)

    def test_metadata_declares_the_data_as_simulated(self) -> None:
        metadata = simulated_terrain_provider().fetch_bbox(ATHENS).metadata
        self.assertTrue(metadata["synthetic"])
        self.assertEqual(metadata["source"], "simulated_terrain")
        self.assertIn("seed", metadata)

    def test_features_carry_the_synthetic_source_tag(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        feature = result.features_by_layer["terrain_contours"][0]
        self.assertEqual(feature["properties"]["hipparchus_source"], "simulated_terrain")
        self.assertFalse(feature["properties"]["index_contour"])

    def test_fetch_is_reproducible_for_a_seed(self) -> None:
        first = simulated_terrain_provider(TerrainFieldSettings(seed=42)).fetch_bbox(ATHENS)
        second = simulated_terrain_provider(TerrainFieldSettings(seed=42)).fetch_bbox(ATHENS)
        self.assertEqual(
            [f["geometry"] for f in first.features_by_layer["terrain_contours"]],
            [f["geometry"] for f in second.features_by_layer["terrain_contours"]],
        )

    def test_a_tiny_window_still_yields_a_readable_number_of_lines(self) -> None:
        """Zooming in must refine the interval, not empty the map."""
        tiny = BBoxQuery(min_lon=23.740, min_lat=37.975, max_lon=23.752, max_lat=37.983)
        result = simulated_terrain_provider().fetch_bbox(tiny)
        lines = result.features_by_layer["terrain_contours"] + result.features_by_layer["terrain_index_contours"]
        self.assertGreater(len(lines), 5)

    def test_sub_cell_specks_are_dropped(self) -> None:
        """Steep ground crowds contours below grid resolution; the crumbs are noise."""
        wide = BBoxQuery(min_lon=23.4, min_lat=37.7, max_lon=24.0, max_lat=38.2)
        settings = TerrainFieldSettings(grid_size=160)
        kept = simulated_terrain_provider(settings).fetch_bbox(wide)
        unfiltered = simulated_terrain_provider(
            TerrainFieldSettings(grid_size=160, min_contour_length_cells=0.0)
        ).fetch_bbox(wide)

        self.assertLess(
            len(kept.features_by_layer["terrain_contours"]),
            len(unfiltered.features_by_layer["terrain_contours"]),
        )
        # The filter trims crumbs, it does not gut the map.
        self.assertGreater(len(kept.features_by_layer["terrain_contours"]), 50)

    def test_other_layers_are_present_but_empty(self) -> None:
        result = simulated_terrain_provider().fetch_bbox(ATHENS)
        self.assertEqual(result.features_by_layer["roads"], [])
        self.assertEqual(result.geojson_by_layer["terrain_contours"]["features"], result.features_by_layer["terrain_contours"])


if __name__ == "__main__":
    unittest.main()
