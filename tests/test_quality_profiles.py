from __future__ import annotations

import unittest

from hipparchus.application.quality import (
    sampling_override,
    DEFAULT_QUALITY_KEY,
    QUALITY_PROFILES,
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
        # Against the default rather than a named profile: this is a test about
        # falling back, not about which profile is default, and hard-coding the
        # label made it fail when the default moved to Print Export.
        fallback = QUALITY_PROFILES[DEFAULT_QUALITY_KEY].label
        self.assertEqual(quality_label_for("nonsense"), fallback)
        self.assertEqual(quality_label_for(None), fallback)

    def test_the_default_samples_the_ground_more_finely_than_a_preview(self) -> None:
        """Fidelity downstream cannot restore detail that was never sampled."""
        self.assertGreater(
            QUALITY_PROFILES[DEFAULT_QUALITY_KEY].sampling_pixels,
            QUALITY_PROFILES["preview_fast"].sampling_pixels,
        )

    def test_sampling_never_goes_backwards_in_menu_order(self) -> None:
        widths = [profile.sampling_pixels for profile in QUALITY_PROFILES.values()]
        self.assertEqual(widths, sorted(widths))

    def test_no_profile_asks_for_more_than_the_mosaic_can_give(self) -> None:
        """256 tiles is 4096 px; past that the budget clips without saying so."""
        for profile in QUALITY_PROFILES.values():
            self.assertLessEqual(profile.sampling_pixels, 4096, profile.key)

class SamplingOverrideTests(unittest.TestCase):
    """The floor has more than one call site, so it lives in one place."""

    def test_the_profile_supplies_the_sampling_when_nobody_set_it(self) -> None:
        profile = QUALITY_PROFILES["export_print"]
        self.assertEqual(
            sampling_override(profile, {}), {"target_pixels": profile.sampling_pixels}
        )

    def test_a_hand_set_sampling_is_left_alone(self) -> None:
        """"Samples across" is an instruction; a floor must not overrule one."""
        self.assertEqual(
            sampling_override(QUALITY_PROFILES["export_print"], {"target_pixels": 800}), {}
        )


if __name__ == "__main__":
    unittest.main()
