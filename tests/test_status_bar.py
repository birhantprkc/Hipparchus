"""The status bar, and the fetch it has to make legible.

A fetch can take five minutes — Overpass is usually all of it — while a single
line says "Idle". Showing each source with its own state and its own elapsed
time makes the slow one obvious, and makes a failure distinguishable from a
wait.
"""

from __future__ import annotations

import tkinter as tk
import unittest

from hipparchus.core.fetch_progress import FetchReporter
from hipparchus.ui import theme
from hipparchus.ui.status_bar import StatusBar, source_label


class LabelTests(unittest.TestCase):
    def test_a_source_is_named_the_way_the_sidebar_names_it(self) -> None:
        """The status bar and the sources list must call the same thing the
        same thing, or they read as two different fetches."""
        self.assertEqual(source_label("overpass"), "OpenStreetMap")
        self.assertEqual(source_label("terrain_tiles"), "Elevation")

    def test_an_unknown_id_falls_back_to_itself(self) -> None:
        self.assertEqual(source_label("something_new"), "something_new")


class StatusBarTestCase(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        self.root.geometry("1000x200")
        theme.set_mode("light")
        self.cancelled = 0
        self.bar = StatusBar(self.root, on_cancel=self._cancel)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.root.deiconify()
        self.root.update()

    def _cancel(self) -> None:
        self.cancelled += 1

    def tearDown(self) -> None:
        self.root.destroy()

    def row_labels(self) -> list[str]:
        return [row.name for row in self.bar.rows()]


class MessageTests(StatusBarTestCase):
    def test_it_shows_what_it_is_told(self) -> None:
        self.bar.set_message("Fetching map data…")
        self.assertEqual(self.bar.message, "Fetching map data…")

    def test_an_error_is_red_and_ordinary_news_is_not(self) -> None:
        self.bar.set_message("All well")
        calm = self.bar.message_colour
        self.bar.set_message("Overpass said no", error=True)
        self.assertNotEqual(self.bar.message_colour, calm)
        self.assertEqual(self.bar.message_colour, theme.current().danger)

    def test_the_message_can_be_selected_and_copied(self) -> None:
        """A status line you can read but not copy is half a status line —
        and it is usually the half with the error in it."""
        self.bar.set_message("Overpass said no", error=True)
        self.root.update()
        self.bar.message_widget.selection_range(0, "end")
        self.assertTrue(self.bar.message_widget.selection_present())
        self.assertEqual(self.bar.message_widget.get(), "Overpass said no")

    def test_the_message_cannot_be_typed_over(self) -> None:
        """Readable and copyable, but not an input: it reports, it does not ask."""
        self.assertEqual(self.bar.message_widget.cget("state"), "readonly")


class ProgressRowTests(StatusBarTestCase):
    def reporter(self) -> FetchReporter:
        reporter = FetchReporter()
        reporter.expect(("overpass", "terrain_tiles"))
        return reporter

    def test_a_fetch_lists_every_source_it_is_waiting_on(self) -> None:
        self.bar.show_progress(self.reporter())
        self.assertEqual(self.row_labels(), ["OpenStreetMap", "Elevation"])

    def test_the_rows_keep_the_order_the_sources_were_asked_for(self) -> None:
        reporter = FetchReporter()
        reporter.expect(("terrain_tiles", "overpass"))
        self.bar.show_progress(reporter)
        self.assertEqual(self.row_labels(), ["Elevation", "OpenStreetMap"])

    def test_each_state_gets_its_own_glyph(self) -> None:
        """Waiting, running, done, failed and cancelled have to be told apart
        at a glance — a failure that looks like a wait is a five-minute lie."""
        reporter = self.reporter()
        reporter.started("overpass")
        self.bar.show_progress(reporter)
        glyphs = {row.name: row.icon for row in self.bar.rows()}
        self.assertNotEqual(glyphs["OpenStreetMap"], glyphs["Elevation"])

    def test_a_finished_source_shows_what_it_brought(self) -> None:
        reporter = self.reporter()
        reporter.started("overpass")
        reporter.finished("overpass", detail="12 431 features")
        self.bar.show_progress(reporter)
        row = next(row for row in self.bar.rows() if row.name == "OpenStreetMap")
        self.assertIn("12 431 features", row.detail)

    def test_a_failure_is_told_apart_from_a_success(self) -> None:
        reporter = self.reporter()
        reporter.started("overpass")
        reporter.failed("overpass", detail="gateway timeout")
        self.bar.show_progress(reporter)
        row = next(row for row in self.bar.rows() if row.name == "OpenStreetMap")
        self.assertEqual(row.icon, "warning")
        self.assertIn("gateway timeout", row.detail)

    def test_a_cancelled_source_says_so(self) -> None:
        reporter = self.reporter()
        reporter.started("overpass")
        reporter.cancelled("overpass")
        self.bar.show_progress(reporter)
        row = next(row for row in self.bar.rows() if row.name == "OpenStreetMap")
        self.assertEqual(row.icon, "cross")

    def test_clearing_takes_the_rows_away(self) -> None:
        self.bar.show_progress(self.reporter())
        self.bar.clear_progress()
        self.assertEqual(self.bar.rows(), [])

    def test_showing_twice_does_not_stack_two_sets_of_rows(self) -> None:
        reporter = self.reporter()
        self.bar.show_progress(reporter)
        reporter.started("overpass")
        self.bar.show_progress(reporter)
        self.assertEqual(len(self.bar.rows()), 2)


class CancelTests(StatusBarTestCase):
    def test_cancel_is_offered_only_while_something_is_running(self) -> None:
        self.assertFalse(self.bar.can_cancel)
        self.bar.set_busy(True)
        self.assertTrue(self.bar.can_cancel)
        self.bar.set_busy(False)
        self.assertFalse(self.bar.can_cancel)

    def test_pressing_it_asks_the_host_to_stop(self) -> None:
        self.bar.set_busy(True)
        self.bar.cancel_button.invoke()
        self.assertEqual(self.cancelled, 1)


class ProvenanceTests(StatusBarTestCase):
    def test_there_is_no_badge_before_anything_is_fetched(self) -> None:
        self.assertEqual(self.bar.provenance, "")

    def test_it_says_what_the_map_is_made_of(self) -> None:
        self.bar.set_provenance("live")
        self.assertEqual(self.bar.provenance, "live")

    def test_it_can_be_taken_away_again(self) -> None:
        self.bar.set_provenance("live")
        self.bar.set_provenance(None)
        self.assertEqual(self.bar.provenance, "")


class CacheTests(StatusBarTestCase):
    def test_the_cache_state_is_shown(self) -> None:
        self.bar.set_cache("hit")
        self.assertIn("hit", self.bar.cache)


class MakersMarkTests(StatusBarTestCase):
    def test_a_missing_logo_leaves_no_gap(self) -> None:
        """The asset is not in this repository yet. Absent must mean absent,
        not a broken-image box in the corner of every window."""
        self.assertIsNone(StatusBar.load_mark(None))
        self.assertIsNone(StatusBar.load_mark("/nowhere/at/all.png"))


if __name__ == "__main__":
    unittest.main()
