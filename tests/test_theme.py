"""The interface's colours and type come from one place, or they drift.

Every one of these is a rule the window used to hold as scattered literals:
forty ``("SF Pro Text", 10)`` tuples that render as a silent fallback off a
Mac, a selection rectangle drawn in whatever blue was nearest to hand, and
five kinds of provenance sharing three colours.
"""

from __future__ import annotations

import re
import unittest

from hipparchus.application.source_stack import SourceStack
from hipparchus.ui import theme

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class PaletteTests(unittest.TestCase):
    def test_both_modes_exist(self) -> None:
        self.assertIsNotNone(theme.palette("light"))
        self.assertIsNotNone(theme.palette("dark"))

    def test_an_unknown_mode_falls_back_to_light_rather_than_raising(self) -> None:
        """A bad HIPPARCHUS_THEME must not be the difference between a window
        and a traceback."""
        self.assertEqual(theme.palette("chartreuse"), theme.palette("light"))

    def test_every_colour_is_a_hex_triplet(self) -> None:
        for mode in ("light", "dark"):
            for field, value in theme.palette(mode).as_dict().items():
                with self.subTest(mode=mode, field=field):
                    self.assertRegex(value, HEX)

    def test_the_two_modes_really_differ(self) -> None:
        light, dark = theme.palette("light"), theme.palette("dark")
        self.assertNotEqual(light.bg, dark.bg)
        self.assertNotEqual(light.text, dark.text)

    def test_light_text_is_darker_than_its_ground_and_dark_text_is_lighter(self) -> None:
        """Catches a palette edited into invisibility."""
        light, dark = theme.palette("light"), theme.palette("dark")
        self.assertLess(theme.luminance(light.text), theme.luminance(light.bg))
        self.assertGreater(theme.luminance(dark.text), theme.luminance(dark.bg))

    def test_body_text_clears_the_contrast_floor_against_its_own_ground(self) -> None:
        for mode in ("light", "dark"):
            palette = theme.palette(mode)
            with self.subTest(mode=mode):
                self.assertGreaterEqual(theme.contrast(palette.text, palette.bg), 7.0)
                self.assertGreaterEqual(theme.contrast(palette.field_text, palette.field), 7.0)

    def test_muted_text_is_still_readable(self) -> None:
        """Secondary is allowed to recede, not to disappear: 4.5:1 is the
        floor for text a person is expected to read."""
        for mode in ("light", "dark"):
            palette = theme.palette(mode)
            with self.subTest(mode=mode):
                self.assertGreaterEqual(theme.contrast(palette.muted, palette.bg), 4.5)


class AccentTests(unittest.TestCase):
    def test_the_accent_is_the_turquoise_the_app_icon_uses(self) -> None:
        """Not the system accent. Everything drawn by hand — the selection
        rectangle, the locator frame, the rubber band — is this one colour, so
        the app does not turn pink because the Finder did."""
        self.assertEqual(theme.palette("light").accent, "#1aafa5")
        self.assertEqual(theme.palette("dark").accent, "#3fcdc2")

    def test_the_accent_is_visible_on_both_grounds(self) -> None:
        for mode in ("light", "dark"):
            palette = theme.palette(mode)
            with self.subTest(mode=mode):
                self.assertGreaterEqual(theme.contrast(palette.accent, palette.bg), 2.0)

    def test_the_accent_on_the_map_is_chosen_against_the_map(self) -> None:
        """The rubber band is drawn on the canvas, whose ground is the scene's
        own background — any of sixteen presets, light or dark, and unrelated
        to whether the *window* is in dark mode. In dark mode the canvas is
        pale paper, so the bright turquoise that reads on a dark panel is the
        one that vanishes on the map. The colour follows what it is drawn on,
        not what the panels are doing."""
        for mode in ("light", "dark"):
            palette = theme.palette(mode)
            with self.subTest(mode=mode):
                accent = theme.accent_for(palette.canvas_bg)
                self.assertGreaterEqual(theme.contrast(accent, palette.canvas_bg), 2.0)

    def test_the_accent_follows_the_ground_it_is_given(self) -> None:
        self.assertEqual(theme.accent_for("#ffffff"), theme.ACCENT_ON_LIGHT)
        self.assertEqual(theme.accent_for("#101010"), theme.ACCENT_ON_DARK)

    def test_both_accents_are_the_same_hue_at_two_weights(self) -> None:
        """Two turquoises, not a turquoise and a fallback: the darker one must
        actually be darker, or 'pick the one that reads' is meaningless."""
        self.assertLess(theme.luminance(theme.ACCENT_ON_LIGHT), theme.luminance(theme.ACCENT_ON_DARK))


class ProvenanceTests(unittest.TestCase):
    def test_every_provenance_the_source_stack_declares_has_a_tint(self) -> None:
        for definition in SourceStack().definitions:
            with self.subTest(source=definition.source_id):
                self.assertIn(definition.provenance, theme.PROVENANCE_TINTS)

    def test_the_five_kinds_are_told_apart_by_colour(self) -> None:
        """They shared three colours between five kinds, so 'measured' and
        'live' — the whole point of the badge — looked identical."""
        kinds = {definition.provenance for definition in SourceStack().definitions}
        self.assertEqual(len(kinds), 5)
        foregrounds = {theme.PROVENANCE_TINTS[kind].foreground for kind in kinds}
        self.assertEqual(len(foregrounds), 5)

    def test_a_badge_is_readable_on_its_own_ground(self) -> None:
        for kind, tint in theme.PROVENANCE_TINTS.items():
            with self.subTest(kind=kind):
                self.assertGreaterEqual(theme.contrast(tint.foreground, tint.background), 4.5)

    def test_an_unknown_provenance_still_draws_something(self) -> None:
        tint = theme.provenance_tint("something-new")
        self.assertRegex(tint.foreground, HEX)
        self.assertRegex(tint.background, HEX)


class TypographyTests(unittest.TestCase):
    def test_a_role_gives_a_font_tkinter_accepts(self) -> None:
        for role in theme.ROLES:
            with self.subTest(role=role):
                font = theme.font(role)
                self.assertIsInstance(font, tuple)
                self.assertIn(len(font), (2, 3))
                self.assertIsInstance(font[0], str)
                self.assertIsInstance(font[1], int)

    def test_the_scale_actually_descends(self) -> None:
        sizes = [theme.font(role)[1] for role in ("title", "heading", "body", "caption", "caption2")]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_headings_are_bold_and_body_is_not(self) -> None:
        self.assertEqual(theme.font("heading")[2], "bold")
        self.assertEqual(len(theme.font("body")), 2)

    def test_an_unknown_role_falls_back_to_body(self) -> None:
        self.assertEqual(theme.font("whatever"), theme.font("body"))

    def test_numbers_get_a_monospaced_face(self) -> None:
        """A coordinate readout that reflows as digits change is unreadable
        while it is changing, which is exactly when it is being read."""
        self.assertNotEqual(theme.digits("body")[0], theme.font("body")[0])

    def test_the_family_is_one_the_platform_actually_has(self) -> None:
        """'SF Pro Text' silently falls back to something else off a Mac, and
        a fallback nobody chose is how an interface ends up in Times."""
        self.assertIn(theme.family("Darwin"), ("SF Pro Text",))
        self.assertIn(theme.family("Windows"), ("Segoe UI",))
        self.assertIn(theme.family("Linux"), ("DejaVu Sans",))


class ColourMathTests(unittest.TestCase):
    def test_luminance_runs_black_to_white(self) -> None:
        self.assertAlmostEqual(theme.luminance("#000000"), 0.0, places=4)
        self.assertAlmostEqual(theme.luminance("#ffffff"), 1.0, places=4)

    def test_contrast_is_symmetric_and_bounded(self) -> None:
        self.assertAlmostEqual(theme.contrast("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(theme.contrast("#ffffff", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(theme.contrast("#123456", "#123456"), 1.0, places=4)

    def test_a_malformed_colour_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(ValueError):
            theme.luminance("not-a-colour")


if __name__ == "__main__":
    unittest.main()
