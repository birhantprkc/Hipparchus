"""A section heading that can hide what is under it.

Gated -- it builds a real `Disclosure` on the one shared root a run is
allowed. See `tests/gui_support.py`.
"""

from __future__ import annotations

import unittest
from tkinter import ttk

from gui_support import reset_root, require_gui, shared_root

from hipparchus.ui.disclosure import Disclosure


class DisclosureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        require_gui()
        self.root = shared_root(400, 400)
        self.addCleanup(reset_root)


class StateTests(DisclosureTestCase):
    def test_starts_expanded_by_default(self) -> None:
        section = Disclosure(self.root, "Sources")
        self.assertTrue(section.expanded)
        self.assertTrue(bool(section.body.winfo_manager()))

    def test_can_start_collapsed(self) -> None:
        section = Disclosure(self.root, "Sources", start_expanded=False)
        self.assertFalse(section.expanded)
        self.root.update()
        self.assertFalse(bool(section.body.winfo_manager()))

    def test_toggle_hides_and_shows_the_body(self) -> None:
        section = Disclosure(self.root, "Sources")
        section.toggle()
        self.root.update()
        self.assertFalse(section.expanded)
        self.assertFalse(bool(section.body.winfo_manager()))

        section.toggle()
        self.root.update()
        self.assertTrue(section.expanded)
        self.assertTrue(bool(section.body.winfo_manager()))

    def test_set_expanded_is_idempotent(self) -> None:
        """Setting the state it is already in must not toggle it."""
        section = Disclosure(self.root, "Sources")
        section.set_expanded(True)
        self.assertTrue(section.expanded)
        section.set_expanded(True)
        self.assertTrue(section.expanded)

    def test_clicking_the_title_toggles_it(self) -> None:
        section = Disclosure(self.root, "Sources")
        section._title.event_generate("<Button-1>")
        self.root.update()
        self.assertFalse(section.expanded)

    def test_the_chevron_is_wired_to_toggle(self) -> None:
        """`test_clicking_the_title_toggles_it` proves the toggle mechanism
        itself works via a real synthetic click; a `tk.Canvas`-based
        `IconButton` does not reliably answer `event_generate` on an
        unmapped root, so this checks the wiring directly instead."""
        section = Disclosure(self.root, "Sources")
        self.assertEqual(section._chevron._command, section.toggle)


class HeaderContentTests(DisclosureTestCase):
    def test_the_title_is_shown_upper_cased(self) -> None:
        section = Disclosure(self.root, "Layers in this map")
        self.assertEqual(section._title.cget("text"), "LAYERS IN THIS MAP")

    def test_a_hint_appears_when_given(self) -> None:
        section = Disclosure(self.root, "Sources", hint="they stack")
        labels = [
            str(child.cget("text"))
            for child in section.header.winfo_children()
            if "TLabel" in child.winfo_class()
        ]
        self.assertIn("they stack", labels)

    def test_the_header_is_a_real_frame_a_caller_can_pack_into(self) -> None:
        """The whole point: All/None beside "Layers in this map" needs
        somewhere that is not this module's business to know about."""
        section = Disclosure(self.root, "Layers in this map")
        extra = ttk.Button(section.header, text="All")
        extra.pack(side="right")
        self.assertIn(extra, section.header.winfo_children())


if __name__ == "__main__":
    unittest.main()
