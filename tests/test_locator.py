"""Choosing an area in a window big enough to aim in.

The rule this exists to keep: **panning and zooming go looking, a click
chooses.** It is what lets you pick a place, zoom out to check you picked the
right one, and still have it picked.
"""

from __future__ import annotations

import unittest

from hipparchus.application.locator import (
    DEFAULT_SPAN,
    describe_area,
    KEY_LEGEND,
    MIN_SPAN,
    Mode,
    area_around,
    area_between,
    span_of,
)
from hipparchus.application.world_view import MAX_LATITUDE

ATHENS = (23.68, 37.94, 23.80, 38.03)


class ClickTests(unittest.TestCase):
    def test_a_click_gives_an_area_centred_on_it(self) -> None:
        west, south, east, north = area_around(23.7, 38.0)
        self.assertAlmostEqual((west + east) / 2, 23.7, places=9)
        self.assertAlmostEqual((south + north) / 2, 38.0, places=9)

    def test_it_keeps_the_size_you_were_working_at(self) -> None:
        """You are choosing a place, not starting again."""
        span = span_of(ATHENS)
        west, south, east, north = area_around(0.0, 0.0, span)
        self.assertAlmostEqual(east - west, span[0], places=9)
        self.assertAlmostEqual(north - south, span[1], places=9)

    def test_a_click_near_the_pole_stays_on_the_earth(self) -> None:
        self.assertLessEqual(area_around(0.0, 85.0, (1.0, 1.0))[3], MAX_LATITUDE)

    def test_a_click_near_the_antimeridian_stays_on_the_earth(self) -> None:
        self.assertLessEqual(area_around(179.9, 0.0, (1.0, 1.0))[2], 180.0)

    def test_a_zero_span_still_gives_something_fetchable(self) -> None:
        west, _, east, _ = area_around(10.0, 10.0, (0.0, 0.0))
        self.assertGreater(east - west, 0.0)


class SpanTests(unittest.TestCase):
    def test_the_span_of_a_frame_is_its_size(self) -> None:
        self.assertAlmostEqual(span_of(ATHENS)[0], 0.12, places=9)

    def test_no_frame_gives_the_default(self) -> None:
        self.assertEqual(span_of(None), DEFAULT_SPAN)

    def test_a_frame_of_no_size_gives_the_default(self) -> None:
        """Rather than a click producing an area of nothing."""
        self.assertEqual(span_of((10.0, 10.0, 10.0, 10.0)), DEFAULT_SPAN)


class DragTests(unittest.TestCase):
    def test_a_dragged_rectangle_becomes_an_area(self) -> None:
        self.assertEqual(
            area_between((23.6, 37.9), (23.9, 38.1)), (23.6, 37.9, 23.9, 38.1)
        )

    def test_it_does_not_matter_which_corner_you_start_from(self) -> None:
        self.assertEqual(
            area_between((23.9, 38.1), (23.6, 37.9)),
            area_between((23.6, 37.9), (23.9, 38.1)),
        )

    def test_a_stray_press_is_not_an_area(self) -> None:
        """Turning one into a sliver nobody meant to draw is worse than
        ignoring it."""
        self.assertIsNone(area_between((23.6, 37.9), (23.6 + MIN_SPAN / 10, 37.9)))

    def test_a_drag_off_the_earth_is_pulled_back(self) -> None:
        area = area_between((-190.0, -90.0), (10.0, 10.0))
        assert area is not None
        self.assertGreaterEqual(area[0], -180.0)
        self.assertGreaterEqual(area[1], -MAX_LATITUDE)


class ModeTests(unittest.TestCase):
    def test_it_starts_out_browsing(self) -> None:
        self.assertFalse(Mode().is_drawing)

    def test_it_can_be_turned_on_and_off(self) -> None:
        mode = Mode()
        self.assertTrue(mode.toggle())
        self.assertFalse(mode.toggle())

    def test_escape_leaves_drawing(self) -> None:
        mode = Mode(is_drawing=True)
        self.assertTrue(mode.leave())
        self.assertFalse(mode.is_drawing)

    def test_escape_while_browsing_reports_that_it_did_nothing(self) -> None:
        """So the key press can be passed on rather than swallowed."""
        self.assertFalse(Mode().leave())

    def test_one_rectangle_then_back_to_browsing(self) -> None:
        """Leaving the mode on makes the next pan draw another area by
        accident, which is how a chosen area gets lost."""
        mode = Mode(is_drawing=True)
        mode.finished_drawing()
        self.assertFalse(mode.is_drawing)


class LegendTests(unittest.TestCase):
    def test_the_keys_are_written_down(self) -> None:
        """This window has no menu bar of its own, so a shortcut nobody is told
        about is a shortcut nobody uses."""
        self.assertTrue(KEY_LEGEND)
        for keys, what in KEY_LEGEND:
            with self.subTest(keys=keys):
                self.assertTrue(keys.strip())
                self.assertTrue(what.strip())

    def test_every_key_the_window_answers_to_is_listed(self) -> None:
        listed = " ".join(keys for keys, _ in KEY_LEGEND)
        for key in ("↑", "⇧", "+", "0", "D", "esc"):
            with self.subTest(key=key):
                self.assertIn(key, listed)




class DescriptionTests(unittest.TestCase):
    """The caption under the locator: where, and how big, at a glance."""

    def test_it_names_the_centre_and_the_span(self) -> None:
        caption = describe_area((23.68, 37.94, 23.80, 38.03))
        self.assertIn("37.98", caption)
        self.assertIn("23.74", caption)
        self.assertIn("0.12", caption)

    def test_hemispheres_are_named_rather_than_signed(self) -> None:
        self.assertIn("N", describe_area((0.0, 10.0, 1.0, 11.0)))
        self.assertIn("S", describe_area((0.0, -11.0, 1.0, -10.0)))
        self.assertIn("E", describe_area((10.0, 0.0, 11.0, 1.0)))
        self.assertIn("W", describe_area((-11.0, 0.0, -10.0, 1.0)))

    def test_the_equator_and_the_meridian_read_as_north_and_east(self) -> None:
        caption = describe_area((-0.5, -0.5, 0.5, 0.5))
        self.assertIn("N", caption)
        self.assertIn("E", caption)

    def test_it_is_one_line(self) -> None:
        self.assertNotIn("\n", describe_area((23.68, 37.94, 23.80, 38.03)))

if __name__ == "__main__":
    unittest.main()
