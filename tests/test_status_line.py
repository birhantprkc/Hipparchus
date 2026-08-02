"""What the status line says, when two things want to say something.

The bar held one string, so everything that had news overwrote everything else.
Exporting wrote "Exported valletta.svg · 21 384 paths" and then a redraw — armed
by the file dialogue closing, not by anything the person did — wrote "Rendering
preview..." over it a few milliseconds later, and "Rendered · 21 layers" over
that. Afterwards the line described a redraw nobody asked for, and the only
durable evidence the export had worked was the Finder window it opened.

The two are not the same kind of thing. A **result** is what something the
person asked for came to; it stands until they ask for something else. A
**report** is the application talking about itself, and may not destroy a
result. What is happening **now** outranks both, because a line that says
"Exported" while a fetch is running is a lie of a different sort.
"""

from __future__ import annotations

import unittest

from hipparchus.application import status_line
from hipparchus.application.status_line import IDLE, StatusState


class EmptyTests(unittest.TestCase):
    def test_a_fresh_line_is_ready_and_calm(self) -> None:
        state = StatusState()
        self.assertEqual(state.text, IDLE)
        self.assertFalse(state.error)


class ResultTests(unittest.TestCase):
    def test_a_result_is_what_the_line_says(self) -> None:
        state = status_line.announce(StatusState(), "Exported valletta.svg")
        self.assertEqual(state.text, "Exported valletta.svg")

    def test_a_failure_carries_its_own_colour(self) -> None:
        state = status_line.announce(StatusState(), "Overpass said no", error=True)
        self.assertTrue(state.error)

    def test_a_newer_result_replaces_an_older_one(self) -> None:
        state = status_line.announce(StatusState(), "Saved the style “Foo”")
        state = status_line.announce(state, "Exported valletta.svg")
        self.assertEqual(state.text, "Exported valletta.svg")

    def test_a_result_clears_the_error_colour_of_the_one_before(self) -> None:
        state = status_line.announce(StatusState(), "Overpass said no", error=True)
        state = status_line.announce(state, "Exported valletta.svg")
        self.assertFalse(state.error)

    def test_announcing_leaves_the_old_state_alone(self) -> None:
        """Nothing here mutates: the caller keeps whatever it was holding."""
        before = status_line.announce(StatusState(), "First")
        status_line.announce(before, "Second")
        self.assertEqual(before.text, "First")


class ReportTests(unittest.TestCase):
    def test_a_report_shows_when_there_is_nothing_better(self) -> None:
        state = status_line.report(StatusState(), "Rendered · 21 layers")
        self.assertEqual(state.text, "Rendered · 21 layers")

    def test_a_report_does_not_destroy_a_result(self) -> None:
        """The bug this file exists for: the export's line survives the redraw
        that follows it."""
        state = status_line.announce(StatusState(), "Exported valletta.svg")
        state = status_line.report(state, "Rendering preview...")
        state = status_line.report(state, "Rendered · 21 layers · 24 926 features")
        self.assertEqual(state.text, "Exported valletta.svg")

    def test_a_result_writes_over_a_report(self) -> None:
        state = status_line.report(StatusState(), "Rendered · 21 layers")
        state = status_line.announce(state, "Exported valletta.svg")
        self.assertEqual(state.text, "Exported valletta.svg")


class ActivityTests(unittest.TestCase):
    def test_what_is_happening_now_outranks_what_happened(self) -> None:
        state = status_line.announce(StatusState(), "Exported valletta.svg")
        state = status_line.start(state, "Fetching map data...")
        self.assertEqual(state.text, "Fetching map data...")

    def test_the_result_returns_when_the_work_ends(self) -> None:
        state = status_line.announce(StatusState(), "Exported valletta.svg")
        state = status_line.start(state, "Rendering preview...")
        state = status_line.finish(state)
        self.assertEqual(state.text, "Exported valletta.svg")

    def test_the_innermost_job_is_the_one_named(self) -> None:
        """A place lookup that finishes mid-fetch must not claim the line, and
        must not take the fetch's name away when it ends."""
        state = status_line.start(StatusState(), "Fetching map data...")
        state = status_line.start(state, "Searching…")
        self.assertEqual(state.text, "Searching…")
        state = status_line.finish(state)
        self.assertEqual(state.text, "Fetching map data...")

    def test_busy_is_whether_anything_is_in_flight(self) -> None:
        state = status_line.start(StatusState(), "Fetching map data...")
        self.assertTrue(state.busy)
        self.assertFalse(status_line.finish(state).busy)

    def test_finishing_what_never_started_is_harmless(self) -> None:
        """`_set_idle` is called on paths that returned before `_set_busy`."""
        state = status_line.finish(StatusState())
        self.assertEqual(state.text, IDLE)
        self.assertFalse(state.busy)

    def test_a_failure_reported_during_work_waits_its_turn(self) -> None:
        state = status_line.start(StatusState(), "Fetching map data...")
        state = status_line.announce(state, "Overpass said no", error=True)
        self.assertEqual(state.text, "Fetching map data...")
        self.assertFalse(state.error, "the colour belongs to the line on show")
        state = status_line.finish(state)
        self.assertEqual(state.text, "Overpass said no")
        self.assertTrue(state.error)


class UndertakeTests(unittest.TestCase):
    def test_asking_for_something_new_retires_the_last_result(self) -> None:
        """Press Render map after an export and the render's own summary is
        what you want to read — the export is over."""
        state = status_line.announce(StatusState(), "Exported valletta.svg")
        state = status_line.undertake(state)
        state = status_line.start(state, "Fetching map data...")
        state = status_line.finish(state)
        state = status_line.report(state, "Rendered · 21 layers · 24 926 features")
        self.assertEqual(state.text, "Rendered · 21 layers · 24 926 features")

    def test_it_clears_the_report_too(self) -> None:
        state = status_line.report(StatusState(), "Rendered · 21 layers")
        self.assertEqual(status_line.undertake(state).text, IDLE)

    def test_it_leaves_work_in_flight_alone(self) -> None:
        """Undertaking is about what has finished, not about what is running."""
        state = status_line.start(StatusState(), "Fetching map data...")
        state = status_line.undertake(state)
        self.assertEqual(state.text, "Fetching map data...")
        self.assertTrue(state.busy)


if __name__ == "__main__":
    unittest.main()
