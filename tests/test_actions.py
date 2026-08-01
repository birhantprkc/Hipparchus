"""The verb table: what the app can do, named once.

The rule this exists to keep is the Mac app's: *every shortcut drives a control
that is also on screen, and a menu item that does nothing teaches distrust.* So
a verb with no handler registered does not appear in the menu at all, rather
than appearing greyed or — worse — appearing live and doing nothing.
"""

from __future__ import annotations

import unittest

from hipparchus.ui import actions as verbs
from hipparchus.ui.shortcuts import sequences_for


class TableTests(unittest.TestCase):
    def test_every_verb_has_a_unique_key(self) -> None:
        keys = [verb.key for verb in verbs.VERBS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_verb_has_a_label_worth_reading(self) -> None:
        for verb in verbs.VERBS:
            with self.subTest(verb=verb.key):
                self.assertTrue(verb.label.strip())
                self.assertEqual(verb.label, verb.label.strip())

    def test_every_verb_belongs_to_a_menu_that_exists(self) -> None:
        for verb in verbs.VERBS:
            with self.subTest(verb=verb.key):
                self.assertIn(verb.menu, verbs.MENUS)

    def test_every_menu_has_at_least_one_verb(self) -> None:
        used = {verb.menu for verb in verbs.VERBS}
        self.assertEqual(used, set(verbs.MENUS))

    def test_every_accelerator_parses_into_real_tk_sequences(self) -> None:
        for verb in verbs.VERBS:
            if not verb.accelerator:
                continue
            for system in ("Darwin", "Windows", "Linux"):
                with self.subTest(verb=verb.key, system=system):
                    sequences = sequences_for(verb.accelerator, system)
                    self.assertTrue(sequences)


class CollisionTests(unittest.TestCase):
    """Two verbs claiming one sequence means one of them silently never fires."""

    def test_no_two_verbs_claim_the_same_sequence(self) -> None:
        for system in ("Darwin", "Windows", "Linux"):
            claimed: dict[str, str] = {}
            for verb in verbs.VERBS:
                if not verb.accelerator:
                    continue
                for sequence in sequences_for(verb.accelerator, system):
                    with self.subTest(system=system, sequence=sequence):
                        self.assertNotIn(
                            sequence,
                            claimed,
                            f"{verb.key} collides with {claimed.get(sequence)}",
                        )
                    claimed[sequence] = verb.key

    def test_the_saved_place_keys_do_not_collide_with_any_verb(self) -> None:
        """⌘1…⌘9 are handed out to places; ⌘0 is Fit to Window, and that is
        exactly the sort of neighbour that goes wrong quietly."""
        for system in ("Darwin", "Windows"):
            verb_sequences = {
                sequence
                for verb in verbs.VERBS
                if verb.accelerator
                for sequence in sequences_for(verb.accelerator, system)
            }
            for spec in verbs.place_accelerators():
                for sequence in sequences_for(spec, system):
                    with self.subTest(system=system, spec=spec):
                        self.assertNotIn(sequence, verb_sequences)


class ActionsTests(unittest.TestCase):
    def test_a_registered_verb_runs(self) -> None:
        calls: list[str] = []
        actions = verbs.Actions()
        actions.register("render_map", lambda: calls.append("ran"))
        self.assertTrue(actions.invoke("render_map"))
        self.assertEqual(calls, ["ran"])

    def test_an_unregistered_verb_is_refused_rather_than_raising(self) -> None:
        """The menu is built before the window finishes; a verb that is not
        wired yet must be a quiet no, not a traceback in front of someone."""
        self.assertFalse(verbs.Actions().invoke("render_map"))

    def test_registering_an_unknown_key_is_a_mistake_worth_hearing_about(self) -> None:
        with self.assertRaises(KeyError):
            verbs.Actions().register("teleport", lambda: None)

    def test_a_verb_can_be_replaced(self) -> None:
        calls: list[str] = []
        actions = verbs.Actions()
        actions.register("render_map", lambda: calls.append("first"))
        actions.register("render_map", lambda: calls.append("second"))
        actions.invoke("render_map")
        self.assertEqual(calls, ["second"])

    def test_it_reports_what_is_wired(self) -> None:
        actions = verbs.Actions()
        self.assertFalse(actions.has("render_map"))
        actions.register("render_map", lambda: None)
        self.assertTrue(actions.has("render_map"))


class MenuAssemblyTests(unittest.TestCase):
    def test_only_wired_verbs_reach_the_menu(self) -> None:
        actions = verbs.Actions()
        actions.register("render_map", lambda: None)
        items = verbs.menu_items("Map", actions)
        self.assertEqual([item.key for item in items], ["render_map"])

    def test_an_empty_menu_yields_nothing_rather_than_a_bare_title(self) -> None:
        self.assertEqual(verbs.menu_items("Map", verbs.Actions()), [])

    def test_items_keep_the_order_they_are_declared_in(self) -> None:
        actions = verbs.Actions()
        for verb in verbs.VERBS:
            actions.register(verb.key, lambda: None)
        for menu in verbs.MENUS:
            declared = [verb.key for verb in verbs.VERBS if verb.menu == menu]
            with self.subTest(menu=menu):
                self.assertEqual([item.key for item in verbs.menu_items(menu, actions)], declared)

    def test_a_separator_never_opens_a_menu(self) -> None:
        """The first item of a menu asking for a rule above it draws a line
        under the title, which reads as an empty section."""
        actions = verbs.Actions()
        for verb in verbs.VERBS:
            actions.register(verb.key, lambda: None)
        for menu in verbs.MENUS:
            items = verbs.menu_items(menu, actions)
            with self.subTest(menu=menu):
                self.assertFalse(items[0].separator_before)

    def test_a_separator_survives_its_neighbour_being_unwired(self) -> None:
        """Phases land one at a time. When the verb above a rule is not built
        yet, the rule must not end up first."""
        first_in_map = next(verb for verb in verbs.VERBS if verb.menu == "Map")
        wired = [verb for verb in verbs.VERBS if verb.menu == "Map" and verb.separator_before]
        if not wired:
            self.skipTest("no separated item in Map")
        actions = verbs.Actions()
        actions.register(wired[0].key, lambda: None)
        items = verbs.menu_items("Map", actions)
        self.assertNotEqual(items[0].key, first_in_map.key)
        self.assertFalse(items[0].separator_before)


class PlaceShortcutTests(unittest.TestCase):
    def test_there_are_nine_of_them(self) -> None:
        self.assertEqual(len(verbs.place_accelerators()), 9)

    def test_they_are_the_number_keys_in_sidebar_order(self) -> None:
        self.assertEqual(verbs.place_accelerators()[0], "Cmd+1")
        self.assertEqual(verbs.place_accelerators()[-1], "Cmd+9")


if __name__ == "__main__":
    unittest.main()
