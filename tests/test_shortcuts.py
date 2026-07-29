"""Accelerators: right modifier, right keys, right label, on every platform."""

from __future__ import annotations

import unittest

from hipparchus.ui.shortcuts import (
    accelerator_label,
    primary_modifier,
    update_map_sequences,
    with_accelerator,
)


class ModifierTests(unittest.TestCase):
    def test_macos_uses_command(self) -> None:
        self.assertEqual(primary_modifier("Darwin"), "Command")

    def test_everything_else_uses_control(self) -> None:
        for system in ("Windows", "Linux", "FreeBSD"):
            with self.subTest(system=system):
                self.assertEqual(primary_modifier(system), "Control")


class SequenceTests(unittest.TestCase):
    def test_macos_binds_command_and_keypad(self) -> None:
        sequences = update_map_sequences("Darwin")
        self.assertIn("<Command-Return>", sequences)
        self.assertIn("<Command-KP_Enter>", sequences)

    def test_macos_also_accepts_control_for_pc_keyboards(self) -> None:
        self.assertIn("<Control-Return>", update_map_sequences("Darwin"))

    def test_windows_binds_control_only(self) -> None:
        sequences = update_map_sequences("Windows")
        self.assertEqual(set(sequences), {"<Control-Return>", "<Control-KP_Enter>"})
        self.assertFalse(any("Command" in sequence for sequence in sequences))

    def test_the_keypad_enter_is_never_forgotten(self) -> None:
        for system in ("Darwin", "Windows", "Linux"):
            with self.subTest(system=system):
                self.assertTrue(any("KP_Enter" in sequence for sequence in update_map_sequences(system)))

    def test_sequences_are_well_formed_tk_events(self) -> None:
        for system in ("Darwin", "Windows"):
            for sequence in update_map_sequences(system):
                with self.subTest(sequence=sequence):
                    self.assertTrue(sequence.startswith("<"))
                    self.assertTrue(sequence.endswith(">"))
                    self.assertEqual(sequence.count("-"), 1)

    def test_no_duplicate_bindings(self) -> None:
        for system in ("Darwin", "Windows", "Linux"):
            sequences = update_map_sequences(system)
            self.assertEqual(len(sequences), len(set(sequences)))


class LabelTests(unittest.TestCase):
    def test_macos_uses_symbols(self) -> None:
        self.assertEqual(accelerator_label("Darwin"), "⌘↩")

    def test_other_platforms_spell_it_out(self) -> None:
        self.assertEqual(accelerator_label("Windows"), "Ctrl+Enter")
        self.assertEqual(accelerator_label("Linux"), "Ctrl+Enter")

    def test_the_button_label_carries_the_hint(self) -> None:
        self.assertEqual(with_accelerator("Update map", "Windows"), "Update map  Ctrl+Enter")
        self.assertTrue(with_accelerator("Update map", "Darwin").startswith("Update map"))

    def test_the_label_is_plain_ascii_where_symbols_may_not_render(self) -> None:
        """A missing glyph on the primary button would read as a hollow box."""
        self.assertTrue(accelerator_label("Windows").isascii())


if __name__ == "__main__":
    unittest.main()
