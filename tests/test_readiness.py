"""Why the button will not work, said before it is pressed.

The application's answer to "nothing is ticked" was a modal dialogue *after*
pressing Render map, and its answer to a bad coordinate was another one. Both
are reasons that were known before the click.

This is the one place that answers it, as a pure function of the choices, so
the button can carry its own reason and the panel can say the same thing in the
place where it can be acted on.
"""

from __future__ import annotations

import unittest

from hipparchus.application.readiness import why_cannot_render
from hipparchus.application.source_stack import SourceStack

ATHENS = ("23.68", "37.94", "23.80", "38.03")


def stack(*enabled: str) -> SourceStack:
    built = SourceStack()
    for definition in built.definitions:
        built.set_enabled(definition.source_id, definition.source_id in enabled)
    return built


class ReadyTests(unittest.TestCase):
    def test_a_ticked_source_and_a_sound_area_can_render(self) -> None:
        self.assertIsNone(why_cannot_render(stack("overpass"), ATHENS))


class SourceTests(unittest.TestCase):
    def test_nothing_ticked_is_the_first_thing_said(self) -> None:
        reason = why_cannot_render(stack(), ATHENS)
        self.assertIsNotNone(reason)
        assert reason is not None
        self.assertIn("source", reason.lower())

    def test_the_reason_says_what_to_do_rather_than_only_what_is_wrong(self) -> None:
        reason = why_cannot_render(stack(), ATHENS)
        assert reason is not None
        self.assertIn("choose", reason.lower())

    def test_a_file_source_with_no_file_does_not_count_as_ticked(self) -> None:
        """`set_enabled` refuses it, so this is really a test that the reason
        follows the stack rather than the click."""
        built = stack()
        built.set_enabled("natural_earth", True)
        self.assertIsNotNone(why_cannot_render(built, ATHENS))


class AreaTests(unittest.TestCase):
    def test_an_empty_coordinate_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("", "37.94", "23.80", "38.03"))
        assert reason is not None
        self.assertIn("coordinate", reason.lower())

    def test_something_that_is_not_a_number_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("east a bit", "37.94", "23.80", "38.03"))
        assert reason is not None
        self.assertIn("number", reason.lower())

    def test_a_longitude_off_the_earth_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("-200", "37.94", "23.80", "38.03"))
        assert reason is not None
        self.assertIn("longitude", reason.lower())

    def test_a_latitude_off_the_earth_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("23.68", "-100", "23.80", "38.03"))
        assert reason is not None
        self.assertIn("latitude", reason.lower())

    def test_west_east_of_east_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("24.0", "37.94", "23.0", "38.03"))
        assert reason is not None
        self.assertIn("west", reason.lower())

    def test_south_north_of_north_is_named(self) -> None:
        reason = why_cannot_render(stack("overpass"), ("23.68", "39.0", "23.80", "38.03"))
        assert reason is not None
        self.assertIn("south", reason.lower())

    def test_an_area_of_no_size_is_refused(self) -> None:
        self.assertIsNotNone(why_cannot_render(stack("overpass"), ("23.68", "37.94", "23.68", "38.03")))


class OrderTests(unittest.TestCase):
    def test_the_sources_are_answered_before_the_coordinates(self) -> None:
        """One reason at a time, and the one nearest the top of the panel
        first: fixing the coordinates would not make an unticked map render."""
        reason = why_cannot_render(stack(), ("", "", "", ""))
        assert reason is not None
        self.assertIn("source", reason.lower())

    def test_the_reason_is_one_sentence(self) -> None:
        """It goes in a tooltip on a disabled button, not a dialogue."""
        for area in (("", "1", "2", "3"), ("-200", "1", "2", "3"), ("2", "1", "1", "3")):
            reason = why_cannot_render(stack("overpass"), area)
            assert reason is not None
            with self.subTest(area=area):
                self.assertLessEqual(reason.count("."), 1)
                self.assertNotIn("\n", reason)


if __name__ == "__main__":
    unittest.main()
