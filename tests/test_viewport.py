"""What the canvas is showing, and what shape to ask for.

Two pieces of arithmetic that decide how the app behaves when you press Render
map, and both of them are the sort that looks right and is wrong by an eighth.

`visible_bounds` answers "what ground is on screen right now" — all four
corners, because a turned viewport's visible ground is a turned rectangle and
two opposite corners do not describe it.

`shaped_to_window` answers "what shape should the request be" — in projected
space, because Mercator stretches latitude and an area that is square in degrees
is distinctly tall on screen.
"""

from __future__ import annotations

import math
import unittest

from hipparchus.application.viewport import (
    fit_margin,
    projected_aspect,
    shaped_to_window,
    visible_bounds,
)
from hipparchus.geometry.projection import ProjectionProfile

ATHENS = (23.68, 37.94, 23.80, 38.03)


class MarginTests(unittest.TestCase):
    def test_the_margin_grows_with_the_canvas(self) -> None:
        self.assertLess(fit_margin(400, 300), fit_margin(1600, 1200))

    def test_a_small_canvas_still_gets_a_usable_margin(self) -> None:
        self.assertGreaterEqual(fit_margin(50, 40), 16.0)

    def test_it_follows_the_shorter_side(self) -> None:
        """A wide, short canvas must not get a margin taller than itself."""
        self.assertEqual(fit_margin(4000, 200), fit_margin(200, 4000))


class VisibleBoundsTests(unittest.TestCase):
    """The screen-to-world call is faked, so the geometry is what is tested
    rather than the renderer."""

    def identity_world(self, x: float, y: float) -> tuple[float, float]:
        return (x, y)

    def test_it_reads_all_four_corners(self) -> None:
        seen: list[tuple[float, float]] = []

        def record(x: float, y: float) -> tuple[float, float]:
            seen.append((x, y))
            return (x, y)

        visible_bounds(width=800, height=600, to_world=record, unproject=lambda x, y: (x, y))
        self.assertEqual(len(seen), 4)
        self.assertEqual(len(set(seen)), 4)

    def test_a_turned_view_is_bounded_by_its_corners_not_by_two_of_them(self) -> None:
        """Rotate the world under the canvas: the ground on screen is a turned
        rectangle, and its bounds are wider than either pair of corners."""

        def turned(x: float, y: float) -> tuple[float, float]:
            angle = math.radians(45)
            return (
                x * math.cos(angle) - y * math.sin(angle),
                x * math.sin(angle) + y * math.cos(angle),
            )

        bounds = visible_bounds(
            width=800, height=800, to_world=turned, unproject=lambda x, y: (x, y)
        )
        assert bounds is not None
        min_lon, min_lat, max_lon, max_lat = bounds
        # A square turned 45° is bounded by a square √2 times as wide.
        self.assertAlmostEqual((max_lon - min_lon) / (max_lat - min_lat), 1.0, places=6)
        self.assertGreater(max_lon - min_lon, 800 - 2 * fit_margin(800, 800))

    def test_the_area_is_inset_by_the_fit_margin(self) -> None:
        """The map is drawn inside the canvas less a margin, so taking the raw
        corners describes an area about an eighth larger than the one on show.
        Fetch that, fit it with a margin again, fetch that — and every press of
        Render map walks the area outwards, which reads as the map slowly
        zooming out on its own."""
        bounds = visible_bounds(
            width=800, height=600, to_world=self.identity_world, unproject=lambda x, y: (x, y)
        )
        assert bounds is not None
        margin = fit_margin(800, 600)
        self.assertAlmostEqual(bounds[0], margin, places=6)
        self.assertAlmostEqual(bounds[2], 800 - margin, places=6)

    def test_a_canvas_too_small_to_draw_in_gives_nothing(self) -> None:
        self.assertIsNone(
            visible_bounds(width=4, height=4, to_world=self.identity_world, unproject=lambda x, y: (x, y))
        )

    def test_a_transform_that_cannot_answer_gives_nothing(self) -> None:
        """Before anything has been drawn there is no transform to ask."""
        self.assertIsNone(
            visible_bounds(width=800, height=600, to_world=lambda x, y: None, unproject=lambda x, y: (x, y))
        )

    def test_the_projection_is_applied(self) -> None:
        profile = ProjectionProfile.from_bbox(ATHENS)
        bounds = visible_bounds(
            width=800,
            height=600,
            to_world=lambda x, y: profile.project_point(23.7 + x / 100000, 37.95 + y / 100000),
            unproject=profile.unproject_point,
        )
        assert bounds is not None
        self.assertAlmostEqual(bounds[0], 23.7 + fit_margin(800, 600) / 100000, places=5)


class ProjectedAspectTests(unittest.TestCase):
    def test_a_box_square_in_degrees_is_taller_than_it_is_wide_on_screen(self) -> None:
        """Mercator stretches latitude by about 1/cos(lat); at Athens a degree
        of latitude is about 1.27 times the height a degree of longitude is
        wide. Shaping by degrees alone would leave the letterbox it was meant
        to remove."""
        aspect = projected_aspect((23.0, 37.5, 24.0, 38.5))
        self.assertLess(aspect, 1.0)
        self.assertAlmostEqual(aspect, math.cos(math.radians(38.0)), delta=0.02)

    def test_at_the_equator_degrees_and_screen_nearly_agree(self) -> None:
        self.assertAlmostEqual(projected_aspect((0.0, -0.5, 1.0, 0.5)), 1.0, delta=0.01)

    def test_a_degenerate_box_has_no_aspect(self) -> None:
        self.assertTrue(math.isnan(projected_aspect((1.0, 1.0, 1.0, 1.0))))


class ShapingTests(unittest.TestCase):
    def test_a_tall_area_is_widened_for_a_wide_window(self) -> None:
        shaped = shaped_to_window((23.70, 37.90, 23.72, 38.02), 16 / 9)
        self.assertGreater(shaped[2] - shaped[0], 23.72 - 23.70)

    def test_a_wide_area_is_heightened_for_a_tall_window(self) -> None:
        shaped = shaped_to_window((23.00, 37.95, 24.00, 38.00), 0.5)
        self.assertGreater(shaped[3] - shaped[1], 38.00 - 37.95)

    def test_it_only_ever_grows(self) -> None:
        """Pressing Render map must not quietly drop part of the area that was
        asked for."""
        original = (23.70, 37.90, 23.72, 38.02)
        for aspect in (0.3, 0.8, 1.0, 1.777, 4.0):
            shaped = shaped_to_window(original, aspect)
            with self.subTest(aspect=aspect):
                self.assertLessEqual(shaped[0], original[0] + 1e-9)
                self.assertLessEqual(shaped[1], original[1] + 1e-9)
                self.assertGreaterEqual(shaped[2], original[2] - 1e-9)
                self.assertGreaterEqual(shaped[3], original[3] - 1e-9)

    def test_it_is_idempotent(self) -> None:
        """Pressing the button twice must not walk the map outwards a little
        each time."""
        once = shaped_to_window(ATHENS, 16 / 9)
        twice = shaped_to_window(once, 16 / 9)
        for first, second in zip(once, twice):
            self.assertAlmostEqual(first, second, places=9)

    def test_the_result_really_is_the_window_s_shape(self) -> None:
        for aspect in (0.5, 1.0, 16 / 9, 3.0):
            shaped = shaped_to_window(ATHENS, aspect)
            with self.subTest(aspect=aspect):
                self.assertAlmostEqual(projected_aspect(shaped), aspect, places=6)

    def test_the_centre_stays_put(self) -> None:
        shaped = shaped_to_window(ATHENS, 16 / 9)
        self.assertAlmostEqual(
            (shaped[0] + shaped[2]) / 2, (ATHENS[0] + ATHENS[2]) / 2, places=9
        )

    def test_an_area_already_the_right_shape_comes_back_untouched(self) -> None:
        shaped = shaped_to_window(ATHENS, projected_aspect(ATHENS))
        self.assertEqual(shaped, ATHENS)

    def test_a_nonsense_aspect_leaves_the_area_alone(self) -> None:
        for aspect in (0.0, -2.0, float("nan"), float("inf")):
            with self.subTest(aspect=aspect):
                self.assertEqual(shaped_to_window(ATHENS, aspect), ATHENS)

    def test_it_never_leaves_the_earth(self) -> None:
        """Widening near a pole or the antimeridian must not produce a box the
        projection cannot draw."""
        for area in ((179.0, 84.0, 179.9, 84.5), (-179.9, -85.0, -179.0, -84.5)):
            shaped = shaped_to_window(area, 8.0)
            with self.subTest(area=area):
                self.assertGreaterEqual(shaped[0], -180.0)
                self.assertLessEqual(shaped[2], 180.0)
                self.assertGreaterEqual(shaped[1], -85.06)
                self.assertLessEqual(shaped[3], 85.06)


if __name__ == "__main__":
    unittest.main()
