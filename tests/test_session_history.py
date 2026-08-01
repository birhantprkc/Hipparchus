"""Undo, and the two rules that make it honest.

**A run of edits that was one intention is one undo.** Typing four coordinates
or dragging a stepper is one act, and an undo stack that makes you press ⌘Z
forty times to take it back is a stack nobody uses.

**Undo of a fetch restores the previous scene rather than re-fetching it.** Undo
must not cost minutes of Overpass time to take back something that cost minutes
of Overpass time. Scenes are held in a bounded store, so undoing very far back
can reach a map that was let go — and then the canvas is honestly empty rather
than silently re-fetched.
"""

from __future__ import annotations

import unittest

from hipparchus.application.session import Area, Session
from hipparchus.application.session_history import SessionHistory


def session(**changes) -> Session:
    return Session().with_changes(**changes)


class ReadingTests(unittest.TestCase):
    def test_a_fresh_history_has_nothing_to_undo(self) -> None:
        history = SessionHistory(Session())
        self.assertFalse(history.can_undo)
        self.assertFalse(history.can_redo)
        self.assertIsNone(history.undo_action_name)

    def test_the_present_is_what_it_was_given(self) -> None:
        start = session(preset_name="Urban Structure")
        self.assertEqual(SessionHistory(start).current.session, start)


class RecordingTests(unittest.TestCase):
    def test_recording_a_change_makes_a_boundary(self) -> None:
        history = SessionHistory(Session())
        self.assertTrue(history.record(session(preset_name="Urban Structure"), "Change Preset", at=1.0))
        self.assertTrue(history.can_undo)

    def test_recording_the_same_state_is_not_an_edit(self) -> None:
        """Observation fires without anything changing, and a no-op must not
        become an entry."""
        history = SessionHistory(Session())
        self.assertFalse(history.record(Session(), "Change Preset", at=1.0))
        self.assertFalse(history.can_undo)

    def test_the_menu_names_the_action_that_made_the_present(self) -> None:
        history = SessionHistory(Session())
        history.record(session(preset_name="Urban Structure"), "Change Preset", at=1.0)
        self.assertEqual(history.undo_action_name, "Change Preset")


class CoalescingTests(unittest.TestCase):
    def test_a_run_under_one_key_is_one_undo(self) -> None:
        history = SessionHistory(Session())
        history.record(session(area=Area(1, 2, 3, 4)), "Change Area", coalescing_key="area", at=1.0)
        history.record(session(area=Area(1, 2, 3, 5)), "Change Area", coalescing_key="area", at=1.1)
        history.record(session(area=Area(1, 2, 3, 6)), "Change Area", coalescing_key="area", at=1.2)

        history.undo()
        self.assertEqual(history.current.session, Session())

    def test_a_pause_ends_the_run(self) -> None:
        """Coming back to a control after a pause is a new intention."""
        history = SessionHistory(Session(), coalescing_window=1.0)
        history.record(session(area=Area(1, 2, 3, 4)), "Change Area", coalescing_key="area", at=1.0)
        history.record(session(area=Area(1, 2, 3, 5)), "Change Area", coalescing_key="area", at=9.0)

        history.undo()
        self.assertEqual(history.current.session.area, Area(1, 2, 3, 4))

    def test_a_different_key_never_merges(self) -> None:
        """Dragging one stepper must not merge with dragging the next."""
        history = SessionHistory(Session())
        history.record(session(source_settings={"a.b": 1.0}), "Change B", coalescing_key="a.b", at=1.0)
        history.record(session(source_settings={"a.c": 1.0}), "Change C", coalescing_key="a.c", at=1.01)

        history.undo()
        self.assertEqual(dict(history.current.session.source_settings), {"a.b": 1.0})

    def test_no_key_never_merges(self) -> None:
        history = SessionHistory(Session())
        history.record(session(preset_name="A"), "Change Preset", at=1.0)
        history.record(session(preset_name="B"), "Change Preset", at=1.01)

        history.undo()
        self.assertEqual(history.current.session.preset_name, "A")

    def test_only_the_first_of_a_run_reports_a_boundary(self) -> None:
        """The caller registers one undo action per True; a run is one."""
        history = SessionHistory(Session())
        made = [
            history.record(session(area=Area(1, 2, 3, 4 + step)), "Change Area", coalescing_key="area", at=1.0 + step / 100)
            for step in range(4)
        ]
        self.assertEqual(made, [True, False, False, False])


class TravellingTests(unittest.TestCase):
    def test_undo_goes_back_and_redo_returns(self) -> None:
        history = SessionHistory(Session())
        history.record(session(preset_name="Urban Structure"), "Change Preset", at=1.0)

        self.assertEqual(history.undo().session, Session())
        self.assertEqual(history.redo().session.preset_name, "Urban Structure")

    def test_undo_at_the_beginning_is_none(self) -> None:
        self.assertIsNone(SessionHistory(Session()).undo())

    def test_redo_with_nothing_undone_is_none(self) -> None:
        self.assertIsNone(SessionHistory(Session()).redo())

    def test_a_new_edit_cuts_the_redo_branch(self) -> None:
        history = SessionHistory(Session())
        history.record(session(preset_name="A"), "Change Preset", at=1.0)
        history.undo()
        history.record(session(preset_name="B"), "Change Preset", at=2.0)
        self.assertFalse(history.can_redo)

    def test_an_edit_after_undo_is_its_own_action(self) -> None:
        """A restored entry is a destination, not an action in progress: the
        next edit must not merge into it."""
        history = SessionHistory(Session())
        history.record(session(area=Area(1, 2, 3, 4)), "Change Area", coalescing_key="area", at=1.0)
        history.undo()
        history.record(session(area=Area(1, 2, 3, 9)), "Change Area", coalescing_key="area", at=1.01)

        history.undo()
        self.assertEqual(history.current.session, Session())

    def test_redo_names_the_action_it_would_put_back(self) -> None:
        history = SessionHistory(Session())
        history.record(session(preset_name="Urban Structure"), "Change Preset", at=1.0)
        history.undo()
        self.assertEqual(history.redo_action_name, "Change Preset")


class FetchTests(unittest.TestCase):
    """The rule that matters most."""

    def test_a_fetch_is_always_a_boundary(self) -> None:
        history = SessionHistory(Session())
        self.assertTrue(history.record_fetch(Session(), scene="scene-1", at=1.0))

    def test_undoing_a_fetch_restores_the_previous_scene_rather_than_refetching(self) -> None:
        history = SessionHistory(Session())
        history.record_fetch(Session(), scene="first map", at=1.0)
        history.record_fetch(session(preset_name="A"), scene="second map", at=2.0)

        snapshot = history.undo()
        self.assertEqual(history.scene(snapshot.scene_token), "first map")

    def test_the_scene_travels_with_the_choices(self) -> None:
        history = SessionHistory(Session())
        history.record_fetch(session(preset_name="A"), scene="map A", at=1.0)
        history.record_fetch(session(preset_name="B"), scene="map B", at=2.0)

        back = history.undo()
        self.assertEqual(back.session.preset_name, "A")
        self.assertEqual(history.scene(back.scene_token), "map A")

        forward = history.redo()
        self.assertEqual(forward.session.preset_name, "B")
        self.assertEqual(history.scene(forward.scene_token), "map B")

    def test_an_edit_after_a_fetch_keeps_the_map_on_screen(self) -> None:
        """Ticking a source does not blank the canvas; the map on screen stays
        until the next fetch replaces it."""
        history = SessionHistory(Session())
        history.record_fetch(Session(), scene="the map", at=1.0)
        history.record(session(preset_name="A"), "Change Preset", at=2.0)
        self.assertEqual(history.scene(history.current.scene_token), "the map")

    def test_a_scene_let_go_still_restores_its_choices(self) -> None:
        """Undoing very far back can reach a map that was evicted. The choices
        come back and the canvas is honestly empty — never silently refetched."""
        history = SessionHistory(Session(), max_scenes=2)
        for step in range(5):
            history.record_fetch(session(preset_name=f"P{step}"), scene=f"map {step}", at=float(step))

        for _ in range(4):
            history.undo()

        self.assertEqual(history.current.session.preset_name, "P0")
        self.assertIsNone(history.scene(history.current.scene_token))

    def test_only_the_newest_scenes_are_kept(self) -> None:
        """A city fetch is tens of megabytes; a hundred of them would not fit."""
        history = SessionHistory(Session(), max_scenes=3)
        for step in range(10):
            history.record_fetch(session(preset_name=f"P{step}"), scene=f"map {step}", at=float(step))
        self.assertLessEqual(history.stored_scenes, 3)

    def test_the_newest_scene_is_never_the_one_dropped(self) -> None:
        history = SessionHistory(Session(), max_scenes=2)
        for step in range(6):
            history.record_fetch(session(preset_name=f"P{step}"), scene=f"map {step}", at=float(step))
        self.assertEqual(history.scene(history.current.scene_token), "map 5")


class BoundsTests(unittest.TestCase):
    def test_the_number_of_entries_is_bounded(self) -> None:
        history = SessionHistory(Session(), max_depth=10)
        for step in range(50):
            history.record(session(preset_name=f"P{step}"), "Change Preset", at=float(step))
        self.assertLessEqual(history.depth, 10)

    def test_undo_still_works_after_the_oldest_entries_are_dropped(self) -> None:
        history = SessionHistory(Session(), max_depth=5)
        for step in range(20):
            history.record(session(preset_name=f"P{step}"), "Change Preset", at=float(step))
        self.assertIsNotNone(history.undo())
        self.assertEqual(history.current.session.preset_name, "P18")

    def test_dropping_entries_releases_the_scenes_they_held(self) -> None:
        history = SessionHistory(Session(), max_depth=3, max_scenes=100)
        for step in range(20):
            history.record_fetch(session(preset_name=f"P{step}"), scene=f"map {step}", at=float(step))
        self.assertLessEqual(history.stored_scenes, 5)


if __name__ == "__main__":
    unittest.main()
