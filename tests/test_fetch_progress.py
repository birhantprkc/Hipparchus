"""Per-source progress, and a cancel that is honest about what it can stop."""

from __future__ import annotations

import unittest

from hipparchus.application.fetch_progress import (
    CancellationToken,
    FetchCancelled,
    FetchReporter,
    SourceProgress,
)


class CancellationTests(unittest.TestCase):
    def test_a_fresh_token_is_not_cancelled(self) -> None:
        token = CancellationToken()
        self.assertFalse(token.cancelled)
        token.raise_if_cancelled()

    def test_cancelling_is_visible_and_raises(self) -> None:
        token = CancellationToken()
        token.cancel()
        self.assertTrue(token.cancelled)
        with self.assertRaises(FetchCancelled):
            token.raise_if_cancelled()

    def test_cancelling_twice_is_harmless(self) -> None:
        token = CancellationToken()
        token.cancel()
        token.cancel()
        self.assertTrue(token.cancelled)

    def test_the_token_is_visible_across_threads(self) -> None:
        import threading

        token = CancellationToken()
        seen: list[bool] = []

        def worker() -> None:
            seen.append(token.cancelled)

        token.cancel()
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(seen, [True])


class SourceProgressTests(unittest.TestCase):
    def test_a_waiting_source_has_no_elapsed_time(self) -> None:
        self.assertEqual(SourceProgress("overpass").elapsed, 0.0)

    def test_summaries_read_as_english(self) -> None:
        progress = SourceProgress("overpass")
        self.assertIn("waiting", progress.summary())
        progress.state = "running"
        progress.started_at = 100.0
        progress.finished_at = 142.0
        self.assertIn("42", progress.summary())
        progress.state = "done"
        self.assertIn("✓", progress.summary())
        progress.state = "cancelled"
        self.assertIn("cancelled", progress.summary())
        progress.state = "failed"
        self.assertIn("failed", progress.summary())

    def test_a_finished_source_stops_counting(self) -> None:
        progress = SourceProgress("terrain_tiles", state="done", started_at=10.0, finished_at=15.0)
        self.assertAlmostEqual(progress.elapsed, 5.0)


class ReporterTests(unittest.TestCase):
    def test_expected_sources_appear_in_order(self) -> None:
        reporter = FetchReporter()
        reporter.expect(("overpass", "terrain_tiles"))
        self.assertEqual(reporter.order, ["overpass", "terrain_tiles"])
        self.assertIn("overpass waiting", reporter.summary())

    def test_the_lifecycle_is_reflected_in_the_summary(self) -> None:
        reporter = FetchReporter()
        reporter.expect(("terrain_tiles",))
        reporter.started("terrain_tiles")
        self.assertTrue(reporter.running)
        reporter.finished("terrain_tiles", detail="20 tiles")
        self.assertFalse(reporter.running)
        self.assertIn("20 tiles", reporter.summary())

    def test_listeners_are_told_about_every_change(self) -> None:
        seen: list[str] = []
        reporter = FetchReporter(on_change=lambda r: seen.append(r.summary()))
        reporter.expect(("overpass",))
        reporter.started("overpass")
        reporter.finished("overpass")
        self.assertEqual(len(seen), 3)

    def test_an_unexpected_source_is_still_recorded(self) -> None:
        reporter = FetchReporter()
        reporter.started("surprise")
        self.assertIn("surprise", reporter.order)

    def test_failure_and_cancellation_are_distinct(self) -> None:
        reporter = FetchReporter()
        reporter.expect(("a", "b"))
        reporter.failed("a", detail="timeout")
        reporter.cancelled("b")
        self.assertEqual(reporter.sources["a"].state, "failed")
        self.assertEqual(reporter.sources["b"].state, "cancelled")
        self.assertFalse(reporter.running)

    def test_expecting_the_same_source_twice_does_not_duplicate_it(self) -> None:
        reporter = FetchReporter()
        reporter.expect(("overpass",))
        reporter.expect(("overpass", "terrain_tiles"))
        self.assertEqual(reporter.order, ["overpass", "terrain_tiles"])

    def test_an_empty_fetch_summarises_to_nothing(self) -> None:
        self.assertEqual(FetchReporter().summary(), "")


if __name__ == "__main__":
    unittest.main()
