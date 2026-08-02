"""Accelerators: right modifier, right keys, right label, on every platform."""

from __future__ import annotations

import unittest

from hipparchus.ui.shortcuts import (
    accelerator_label,
    label_for,
    primary_modifier,
    sequences_for,
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


class GeneralAcceleratorTests(unittest.TestCase):
    """The whole keyboard map, not just Render map.

    Every one of these is a shortcut the Mac app has and this one is growing;
    they have to be right on a platform this is not being written on.
    """

    def test_the_primary_modifier_follows_the_platform(self) -> None:
        self.assertIn("<Command-Key-l>", sequences_for("Cmd+L", "Darwin"))
        self.assertIn("<Control-Key-l>", sequences_for("Cmd+L", "Windows"))
        self.assertFalse(any("Command" in s for s in sequences_for("Cmd+L", "Linux")))

    def test_shift_reaches_the_shifted_keysym(self) -> None:
        """With shift held the keysym is 'E', not 'e'. Binding the lower-case
        one produces a shortcut that never fires."""
        sequences = sequences_for("Cmd+Shift+E", "Darwin")
        self.assertTrue(any(s.endswith("-E>") for s in sequences))
        self.assertFalse(any(s.endswith("-e>") for s in sequences))

    def test_option_is_spelled_the_way_each_platform_spells_it(self) -> None:
        self.assertTrue(any("Option" in s for s in sequences_for("Cmd+Alt+E", "Darwin")))
        self.assertTrue(any("Alt" in s for s in sequences_for("Cmd+Alt+E", "Windows")))

    def test_option_is_not_bound_twice_on_a_mac(self) -> None:
        """Tk on Aqua treats Option and Alt as the same modifier bit, so
        binding both patterns fires the action twice for one press."""
        sequences = sequences_for("Cmd+Alt+E", "Darwin")
        self.assertFalse(any("Alt" in s for s in sequences))

    def test_punctuation_becomes_the_tk_keysym_rather_than_the_character(self) -> None:
        for spec, keysym in (
            ("Cmd+.", "period"),
            ("Cmd+,", "comma"),
            ("Cmd+[", "bracketleft"),
            ("Cmd+]", "bracketright"),
            ("Cmd+-", "minus"),
        ):
            with self.subTest(spec=spec):
                self.assertTrue(
                    any(s.endswith(f"-{keysym}>") for s in sequences_for(spec, "Darwin")),
                    f"{spec} -> {sequences_for(spec, 'Darwin')}",
                )

    def test_zoom_in_also_answers_to_the_unshifted_key(self) -> None:
        """⌘+ is really ⌘⇧= on most keyboards, and people press ⌘= for it."""
        sequences = sequences_for("Cmd++", "Darwin")
        self.assertTrue(any(s.endswith("-plus>") for s in sequences))
        self.assertTrue(any(s.endswith("-equal>") for s in sequences))

    def test_digits_bind_as_keys_not_as_mouse_buttons(self) -> None:
        """Tk reads a bare digit 1–5 as a button number, so <Command-1> binds
        Command-click. ⌘1…⌘5 for the saved places would have done nothing at
        all while ⌘6…⌘9 worked — the explicit Key field is what prevents it."""
        for digit in "123456789":
            with self.subTest(digit=digit):
                for sequence in sequences_for(f"Cmd+{digit}", "Darwin"):
                    self.assertIn("-Key-", sequence)

    def test_every_sequence_names_the_key_field_explicitly(self) -> None:
        for spec in ("Cmd+Return", "Cmd+.", "Cmd+E", "Cmd+Shift+E", "Cmd++", "Cmd+["):
            for system in ("Darwin", "Windows"):
                for sequence in sequences_for(spec, system):
                    with self.subTest(spec=spec, sequence=sequence):
                        self.assertIn("-Key-", sequence)

    def test_digits_bind_as_digits(self) -> None:
        self.assertIn("<Command-Key-1>", sequences_for("Cmd+1", "Darwin"))

    def test_every_sequence_is_a_well_formed_tk_event(self) -> None:
        specs = ("Cmd+Return", "Cmd+.", "Cmd+L", "Cmd+Shift+V", "Cmd+Alt+E", "Cmd++", "Cmd+[", "Cmd+1")
        for system in ("Darwin", "Windows", "Linux"):
            for spec in specs:
                for sequence in sequences_for(spec, system):
                    with self.subTest(spec=spec, system=system, sequence=sequence):
                        self.assertTrue(sequence.startswith("<"))
                        self.assertTrue(sequence.endswith(">"))
                        self.assertNotIn(" ", sequence)

    def test_no_spec_binds_the_same_sequence_twice(self) -> None:
        for system in ("Darwin", "Windows", "Linux"):
            for spec in ("Cmd+Return", "Cmd++", "Cmd+Shift+E"):
                sequences = sequences_for(spec, system)
                with self.subTest(spec=spec, system=system):
                    self.assertEqual(len(sequences), len(set(sequences)))

    def test_two_different_verbs_never_claim_the_same_sequence(self) -> None:
        """Export SVG is ⌘E and Export PDF is ⇧⌘E; if those collided one of
        them would silently never happen."""
        for system in ("Darwin", "Windows"):
            svg = set(sequences_for("Cmd+E", system))
            pdf = set(sequences_for("Cmd+Shift+E", system))
            png = set(sequences_for("Cmd+Alt+E", system))
            with self.subTest(system=system):
                self.assertFalse(svg & pdf)
                self.assertFalse(svg & png)
                self.assertFalse(pdf & png)


class GeneralLabelTests(unittest.TestCase):
    def test_macos_spells_shortcuts_in_symbols(self) -> None:
        self.assertEqual(label_for("Cmd+Return", "Darwin"), "⌘↩")
        self.assertEqual(label_for("Cmd+Shift+E", "Darwin"), "⇧⌘E")
        self.assertEqual(label_for("Cmd+Alt+E", "Darwin"), "⌥⌘E")
        self.assertEqual(label_for("Cmd+[", "Darwin"), "⌘[")
        self.assertEqual(label_for("Cmd+1", "Darwin"), "⌘1")

    def test_the_modifier_order_is_the_one_macos_uses(self) -> None:
        """⇧⌥⌘ — the platform's own order, not the order they were typed in."""
        self.assertEqual(label_for("Cmd+Alt+Shift+E", "Darwin"), "⇧⌥⌘E")

    def test_other_platforms_spell_it_out_in_ascii(self) -> None:
        self.assertEqual(label_for("Cmd+Return", "Windows"), "Ctrl+Enter")
        self.assertEqual(label_for("Cmd+Shift+E", "Windows"), "Ctrl+Shift+E")
        self.assertTrue(label_for("Cmd+Alt+E", "Linux").isascii())

    def test_punctuation_reads_as_a_word_where_the_symbol_would_confuse(self) -> None:
        self.assertEqual(label_for("Cmd++", "Windows"), "Ctrl+Plus")
        self.assertEqual(label_for("Cmd+-", "Windows"), "Ctrl+Minus")

    def test_the_old_render_map_label_still_agrees_with_the_general_one(self) -> None:
        for system in ("Darwin", "Windows", "Linux"):
            with self.subTest(system=system):
                self.assertEqual(accelerator_label(system), label_for("Cmd+Return", system))


if __name__ == "__main__":
    unittest.main()
