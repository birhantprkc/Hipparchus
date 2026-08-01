from __future__ import annotations

import unittest

from hipparchus.application.quality import (
    quality_label_for,
    quality_menu_labels,
    quality_mode_key,
    quality_profile,
)


class QualityProfileTests(unittest.TestCase):
    def test_legacy_quality_values_normalize(self) -> None:
        self.assertEqual(quality_mode_key("preview"), "preview_fast")
        self.assertEqual(quality_mode_key("export"), "export_clean")

    def test_menu_labels_map_to_profiles(self) -> None:
        for label in quality_menu_labels():
            self.assertIn(quality_profile(label).key, {"preview_fast", "preview_high", "export_clean", "export_print"})




class LabelLookupTests(unittest.TestCase):
    """The session stores a key and the dropdown shows a label. Restoring a
    session has to turn one back into the other, or a restored window shows a
    quality it is not using."""

    def test_a_key_gives_its_label(self) -> None:
        self.assertEqual(quality_label_for("preview_fast"), "Fast Preview")
        self.assertEqual(quality_label_for("export_print"), "Print Export")

    def test_it_round_trips_with_the_key_lookup(self) -> None:
        for label in quality_menu_labels():
            with self.subTest(label=label):
                self.assertEqual(quality_label_for(quality_mode_key(label)), label)

    def test_every_key_has_a_label_and_every_label_a_key(self) -> None:
        for label in quality_menu_labels():
            self.assertIn(quality_label_for(quality_mode_key(label)), quality_menu_labels())

    def test_an_unknown_key_falls_back_rather_than_showing_a_blank(self) -> None:
        self.assertEqual(quality_label_for("nonsense"), "Fast Preview")
        self.assertEqual(quality_label_for(None), "Fast Preview")

if __name__ == "__main__":
    unittest.main()
