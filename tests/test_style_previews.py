"""Style thumbnails are drawn from the presets, so they cannot advertise a lie."""

from __future__ import annotations

import unittest

from hipparchus.application.presets import default_preset, preset_names
from hipparchus.application.style_previews import (
    featured_names,
    ring_geometry,
    swatch_for,
    swatches,
)


class FeaturedTests(unittest.TestCase):
    def test_every_featured_preset_exists(self) -> None:
        available = set(preset_names())
        for name in featured_names():
            self.assertIn(name, available)

    def test_the_picker_is_short_enough_to_scan(self) -> None:
        self.assertGreaterEqual(len(featured_names()), 4)
        self.assertLessEqual(len(featured_names()), 8)


class SwatchTests(unittest.TestCase):
    def test_a_swatch_takes_its_ground_from_the_preset(self) -> None:
        for name in featured_names():
            with self.subTest(preset=name):
                self.assertEqual(swatch_for(name).background, default_preset(name).style_profile.background)

    def test_a_dark_preset_is_recognised_as_dark(self) -> None:
        self.assertTrue(swatch_for("Night").is_dark)
        self.assertFalse(swatch_for("Clean Atlas").is_dark)

    def test_contour_colour_comes_from_the_contour_style(self) -> None:
        style = default_preset("Contour Study").style_profile.layer_styles["terrain_contours"]
        self.assertEqual(swatch_for("Contour Study").contour_color, style.stroke_color)

    def test_an_accented_preset_draws_mixed_weights(self) -> None:
        widths = swatch_for("Contour Study").contour_widths
        self.assertGreater(len(set(widths)), 1)

    def test_a_uniform_preset_draws_uniform_weights(self) -> None:
        """Relief Sheet accents nothing, and the picker should show that."""
        self.assertEqual(len(set(swatch_for("Relief Sheet").contour_widths)), 1)

    def test_only_a_tinted_preset_carries_band_colours(self) -> None:
        self.assertTrue(swatch_for("Hypsometric Relief").band_colors)
        self.assertEqual(swatch_for("Contour Study").band_colors, ())

    def test_the_band_ramp_runs_low_to_high(self) -> None:
        style = default_preset("Hypsometric Relief").style_profile.layer_styles["elevation_bands"]
        colors = swatch_for("Hypsometric Relief").band_colors
        self.assertEqual(colors[0], style.fill_color)
        self.assertEqual(colors[-1], style.fill_color_high)

    def test_every_preset_can_be_drawn(self) -> None:
        for name in preset_names():
            with self.subTest(preset=name):
                swatch = swatch_for(name)
                self.assertTrue(swatch.contour_widths)
                self.assertGreater(min(swatch.contour_widths), 0.0)

    def test_swatches_returns_one_per_featured_preset(self) -> None:
        self.assertEqual(len(swatches()), len(featured_names()))


class RingTests(unittest.TestCase):
    def test_rings_stay_inside_the_thumbnail(self) -> None:
        for index in range(5):
            for x, y in ring_geometry(index, 5):
                self.assertGreaterEqual(x, -0.05)
                self.assertLessEqual(x, 1.05)
                self.assertGreaterEqual(y, -0.05)
                self.assertLessEqual(y, 1.05)

    def test_rings_nest_inwards(self) -> None:
        def extent(points):
            xs = [x for x, _ in points]
            return max(xs) - min(xs)

        self.assertGreater(extent(ring_geometry(0, 5)), extent(ring_geometry(3, 5)))

    def test_rings_are_closed_loops(self) -> None:
        points = ring_geometry(1, 5)
        self.assertAlmostEqual(points[0][0], points[-1][0], places=6)
        self.assertAlmostEqual(points[0][1], points[-1][1], places=6)

    def test_a_single_ring_is_safe(self) -> None:
        self.assertTrue(ring_geometry(0, 1))


if __name__ == "__main__":
    unittest.main()
