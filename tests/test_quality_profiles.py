from __future__ import annotations

import unittest

from hipparchus.application.quality import quality_menu_labels, quality_mode_key, quality_profile


class QualityProfileTests(unittest.TestCase):
    def test_legacy_quality_values_normalize(self) -> None:
        self.assertEqual(quality_mode_key("preview"), "preview_fast")
        self.assertEqual(quality_mode_key("export"), "export_clean")

    def test_menu_labels_map_to_profiles(self) -> None:
        for label in quality_menu_labels():
            self.assertIn(quality_profile(label).key, {"preview_fast", "preview_high", "export_clean", "export_print"})


if __name__ == "__main__":
    unittest.main()
