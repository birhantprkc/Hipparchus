"""The menu bar, built from the verb table and bound to the same handlers.

Built against a real Tk menu rather than a mock: the failures worth catching
here are Tk's own — an accelerator string it will not render, a cascade added
to the wrong parent, a binding that never reaches `bind_all`.
"""

from __future__ import annotations

import tkinter as tk
import unittest

from gui_support import require_focus_tests, require_gui, show_offscreen
from hipparchus.ui import actions as verbs
from hipparchus.ui import menubar
from hipparchus.ui.shortcuts import sequences_for


def _settle_focus(root: tk.Tk, attempts: int = 50) -> bool:
    """Wait until the window really has keyboard focus.

    `focus_force` asks; it does not guarantee arrival by the next line. With
    other test roots about and the process not frontmost, a synthetic key can
    land nowhere — which made these tests fail about one run in six. Waiting for
    the focus to be observable makes the press deterministic.
    """
    for _ in range(attempts):
        root.focus_force()
        root.update()
        if root.focus_displayof() is not None:
            return True
    return False


class FocusTestCase:
    """Mixin for the tests that need the window to hold the keyboard."""

    def setUp(self) -> None:  # type: ignore[override]
        require_focus_tests()
        super().setUp()  # type: ignore[misc]


class MenuBarTestCase(unittest.TestCase):
    def setUp(self) -> None:
        require_gui()
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        self.calls: list[str] = []
        self.actions = verbs.Actions()
        for verb in verbs.VERBS:
            self.actions.register(verb.key, lambda key=verb.key: self.calls.append(key))

    def tearDown(self) -> None:
        self.root.destroy()

    def send(self, sequence: str) -> None:
        """Press a key at the window, deterministically.

        `deiconify` alone does not give the window keyboard focus — with other
        test roots about and the process not frontmost it may have none, and the
        key lands nowhere. That made these tests fail about one run in ten,
        which is worse than not having them.
        """
        _settle_focus(self.root)
        self.root.event_generate(sequence, when="now")
        self.root.update()

    def labels(self, menu: tk.Menu) -> list[str]:
        return [label for _, label in self.entries(menu)]

    def entries(self, menu: tk.Menu) -> list[tuple[int, str]]:
        """(index, label) pairs. The index is the menu's own, which is not the
        position in this list: separators occupy indices and carry no label."""
        end = menu.index("end")
        found = []
        for index in range(0 if end is None else int(end) + 1):
            if menu.type(index) in ("command", "cascade"):
                found.append((index, menu.entrycget(index, "label")))
        return found

    def index_of(self, menu: tk.Menu, label: str) -> int:
        return next(index for index, found in self.entries(menu) if found == label)


class StructureTests(MenuBarTestCase):
    def test_the_menus_are_the_ones_declared(self) -> None:
        bar = menubar.build(self.root, self.actions)
        self.assertEqual(self.labels(bar), list(verbs.MENUS))

    def test_the_window_actually_gets_the_menu(self) -> None:
        bar = menubar.build(self.root, self.actions)
        self.assertEqual(str(self.root.cget("menu")), str(bar))

    def test_every_wired_verb_appears_under_its_own_menu(self) -> None:
        bar = menubar.build(self.root, self.actions)
        for menu_name in verbs.MENUS:
            labels = self.labels(menubar.submenu(bar, menu_name))
            for verb in verbs.VERBS:
                if verb.menu != menu_name:
                    continue
                with self.subTest(verb=verb.key):
                    self.assertIn(verb.label, labels)

    def test_an_unwired_verb_is_absent_rather_than_greyed(self) -> None:
        """A menu item that does nothing teaches distrust."""
        actions = verbs.Actions()
        actions.register("render_map", lambda: None)
        bar = menubar.build(self.root, actions)
        labels = self.labels(menubar.submenu(bar, "Map"))
        self.assertIn("Render Map", labels)
        self.assertNotIn("Export SVG…", labels)

    def test_a_menu_with_nothing_wired_is_not_shown_at_all(self) -> None:
        actions = verbs.Actions()
        actions.register("render_map", lambda: None)
        bar = menubar.build(self.root, actions)
        self.assertEqual(self.labels(bar), ["Map"])


class InvocationTests(MenuBarTestCase):
    def test_choosing_an_item_runs_its_verb(self) -> None:
        bar = menubar.build(self.root, self.actions)
        menu = menubar.submenu(bar, "Map")
        menu.invoke(self.index_of(menu, "Render Map"))
        self.assertEqual(self.calls, ["render_map"])

    def test_the_menu_and_the_shortcut_run_the_same_handler(self) -> None:
        """Two copies of an action become two behaviours within a release."""
        bar = menubar.build(self.root, self.actions)
        menu = menubar.submenu(bar, "View")
        menu.invoke(self.index_of(menu, "Zoom In"))
        self.assertEqual(self.calls, ["zoom_in"])


class AcceleratorTests(FocusTestCase, MenuBarTestCase):
    def test_items_display_their_shortcut(self) -> None:
        bar = menubar.build(self.root, self.actions)
        menu = menubar.submenu(bar, "Map")
        index = self.index_of(menu, "Render Map")
        self.assertTrue(menu.entrycget(index, "accelerator"))

    def test_an_item_without_a_shortcut_shows_none(self) -> None:
        bar = menubar.build(self.root, self.actions)
        menu = menubar.submenu(bar, "View")
        index = self.index_of(menu, "North Up")
        self.assertFalse(menu.entrycget(index, "accelerator"))

    def test_every_shortcut_actually_runs_its_verb(self) -> None:
        """Tk's menu accelerator is decoration — it binds nothing. An item can
        promise ⌘E and do nothing at all if the binding is forgotten. Asserted
        by pressing the key, because Tk stores bindings under normalised names
        of its own and comparing strings would prove nothing."""
        menubar.build(self.root, self.actions)
        show_offscreen(self.root)
        for verb in verbs.VERBS:
            if not verb.accelerator:
                continue
            self.calls.clear()
            for sequence in sequences_for(verb.accelerator):
                self.send(sequence)
            with self.subTest(verb=verb.key):
                self.assertIn(verb.key, self.calls)

    def test_no_shortcut_is_bound_as_a_mouse_button(self) -> None:
        """Tk reads a bare digit 1–5 as a button number. ⌘1…⌘5 landing on
        Command-click is silent: the menu still draws the shortcut."""
        menubar.build(self.root, self.actions, on_place=lambda name: None)
        stray = [s for s in self.root.bind_all() if "Button" in s]
        self.assertEqual(stray, [])

    def test_pressing_the_key_runs_the_verb(self) -> None:
        menubar.build(self.root, self.actions)
        show_offscreen(self.root)
        self.send(sequences_for("Cmd+.")[0])
        self.assertIn("cancel_fetch", self.calls)


class SavedPlacesTests(MenuBarTestCase):
    def test_the_places_submenu_appears_when_a_handler_is_given(self) -> None:
        bar = menubar.build(self.root, self.actions, on_place=lambda name: self.calls.append(name))
        self.assertIn(menubar.PLACES_LABEL, self.labels(menubar.submenu(bar, "Map")))

    def test_it_is_absent_when_no_handler_is_given(self) -> None:
        bar = menubar.build(self.root, self.actions)
        self.assertNotIn(menubar.PLACES_LABEL, self.labels(menubar.submenu(bar, "Map")))

    def test_every_saved_place_is_listed(self) -> None:
        from hipparchus.application import places

        bar = menubar.build(self.root, self.actions, on_place=lambda name: self.calls.append(name))
        labels = self.labels(menubar.places_menu(bar))
        self.assertEqual(len(labels), len(places.PLACES))

    def test_the_first_nine_carry_a_number_key(self) -> None:
        bar = menubar.build(self.root, self.actions, on_place=lambda name: self.calls.append(name))
        menu = menubar.places_menu(bar)
        self.assertTrue(menu.entrycget(0, "accelerator"))
        self.assertTrue(menu.entrycget(8, "accelerator"))

    def test_past_the_ninth_there_is_no_shortcut_rather_than_an_invented_one(self) -> None:
        """Nine is where the conventional run of number keys stops."""
        bar = menubar.build(self.root, self.actions, on_place=lambda name: self.calls.append(name))
        menu = menubar.places_menu(bar)
        self.assertFalse(menu.entrycget(9, "accelerator"))

    def test_choosing_a_place_passes_its_name(self) -> None:
        from hipparchus.application import places

        chosen: list[str] = []
        bar = menubar.build(self.root, self.actions, on_place=chosen.append)
        menubar.places_menu(bar).invoke(1)
        self.assertEqual(chosen, [places.PLACES[1].name])

    def test_every_number_key_chooses_its_own_place(self) -> None:
        """⌘1…⌘5 were the ones that would have silently done nothing."""
        from hipparchus.application import places

        for position, spec in enumerate(verbs.place_accelerators()):
            chosen: list[str] = []
            menubar.build(self.root, self.actions, on_place=chosen.append)
            show_offscreen(self.root)
            self.root.update()
            # One sequence at a time: on macOS both the Command and the
            # Control variant are bound on purpose, and firing both would
            # rightly count two.
            for sequence in sequences_for(spec):
                chosen.clear()
                self.send(sequence)
                with self.subTest(spec=spec, sequence=sequence):
                    self.assertEqual(chosen, [places.PLACES[position].name])

    def test_pressing_a_number_key_chooses_that_place(self) -> None:
        from hipparchus.application import places

        chosen: list[str] = []
        menubar.build(self.root, self.actions, on_place=chosen.append)
        show_offscreen(self.root)
        self.send(sequences_for("Cmd+3")[0])
        self.assertEqual(chosen, [places.PLACES[2].name])


class RebuildTests(FocusTestCase, MenuBarTestCase):
    def test_building_twice_does_not_leave_two_menu_bars(self) -> None:
        menubar.build(self.root, self.actions)
        bar = menubar.build(self.root, self.actions)
        self.assertEqual(self.labels(bar), list(verbs.MENUS))

    def test_building_twice_does_not_fire_a_verb_twice(self) -> None:
        """Stale bindings from the first build would double every shortcut."""
        menubar.build(self.root, self.actions)
        menubar.build(self.root, self.actions)
        show_offscreen(self.root)
        self.send(sequences_for("Cmd+.")[0])
        self.assertEqual(self.calls.count("cancel_fetch"), 1)


if __name__ == "__main__":
    unittest.main()
