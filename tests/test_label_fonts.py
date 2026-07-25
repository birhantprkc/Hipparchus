"""Tests for label font fallback across writing systems."""

from __future__ import annotations

import unittest

try:
    import skia  # type: ignore  # noqa: F401

    SKIA_AVAILABLE = True
except Exception:  # noqa: BLE001
    SKIA_AVAILABLE = False

from hipparchus.rendering.skia_renderer import _typeface_for_text


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class LabelFontFallbackTests(unittest.TestCase):
    def test_latin_needs_no_fallback(self) -> None:
        self.assertIsNone(_typeface_for_text("Kyoto Station"))

    def test_empty_text_needs_no_fallback(self) -> None:
        self.assertIsNone(_typeface_for_text(""))

    def test_greek_is_covered_by_the_default_face(self) -> None:
        """Greek and Cyrillic live in the default face, so no fallback."""
        self.assertIsNone(_typeface_for_text("Αθήνα"))

    def test_japanese_resolves_a_covering_typeface(self) -> None:
        typeface = _typeface_for_text("京都駅")

        self.assertIsNotNone(typeface)
        # A non-zero glyph id is the whole point: zero renders as tofu.
        self.assertNotEqual(typeface.unicharToGlyph(ord("京")), 0)

    def test_mixed_script_resolves_on_the_uncovered_character(self) -> None:
        typeface = _typeface_for_text("Kyoto 京都")

        self.assertIsNotNone(typeface)
        self.assertNotEqual(typeface.unicharToGlyph(ord("京")), 0)

    def test_korean_resolves_a_covering_typeface(self) -> None:
        typeface = _typeface_for_text("서울역")

        self.assertIsNotNone(typeface)
        self.assertNotEqual(typeface.unicharToGlyph(ord("서")), 0)

    def test_lookup_is_cached(self) -> None:
        first = _typeface_for_text("京都")
        second = _typeface_for_text("京都")

        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
