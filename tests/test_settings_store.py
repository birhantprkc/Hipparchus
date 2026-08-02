"""Preferences, and the clamping that keeps a typed number meaningful.

The file is editable by hand, which is a feature. A zero in the cache ceiling
meaning "keep nothing" is not, and neither is a rate of zero requests a second,
which would stall every fetch and look like a hang.

Shared with the macOS app: same file, same format, same field names.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hipparchus.core.settings_store import (
    MAX_DEVICE_SCALE,
    MAX_RPS,
    MIN_CACHE_MB,
    MIN_DEVICE_SCALE,
    MIN_RPS,
    SettingsStore,
    UserSettings,
    clamp,
    storage_locations,
)


class DefaultsTests(unittest.TestCase):
    def test_the_defaults_are_usable(self) -> None:
        settings = UserSettings()
        self.assertGreaterEqual(settings.cache_size_limit_mb, MIN_CACHE_MB)
        self.assertGreaterEqual(settings.provider_rps_limit, MIN_RPS)

    def test_settings_are_a_value(self) -> None:
        original = UserSettings()
        changed = original.with_changes(cache_size_limit_mb=512)
        self.assertEqual(original.cache_size_limit_mb, UserSettings().cache_size_limit_mb)
        self.assertEqual(changed.cache_size_limit_mb, 512)


class ClampTests(unittest.TestCase):
    def test_a_cache_ceiling_of_zero_is_refused(self) -> None:
        """It would mean "keep nothing", which is never what somebody typing a
        number into that box wants."""
        self.assertEqual(clamp(UserSettings(cache_size_limit_mb=0)).cache_size_limit_mb, MIN_CACHE_MB)

    def test_a_negative_ceiling_is_refused(self) -> None:
        self.assertEqual(clamp(UserSettings(cache_size_limit_mb=-9)).cache_size_limit_mb, MIN_CACHE_MB)

    def test_a_rate_of_zero_is_refused(self) -> None:
        """It would stall every fetch, which reads as a hang rather than a
        setting."""
        self.assertGreaterEqual(clamp(UserSettings(provider_rps_limit=0.0)).provider_rps_limit, MIN_RPS)

    def test_an_absurd_rate_is_capped(self) -> None:
        """Overpass runs on donated hardware."""
        self.assertLessEqual(clamp(UserSettings(provider_rps_limit=9999.0)).provider_rps_limit, MAX_RPS)

    def test_a_label_size_nobody_can_read_is_refused(self) -> None:
        self.assertGreaterEqual(clamp(UserSettings(label_font_size=1)).label_font_size, 6)
        self.assertLessEqual(clamp(UserSettings(label_font_size=400)).label_font_size, 24)

    def test_device_scale_stays_in_range(self) -> None:
        self.assertGreaterEqual(clamp(UserSettings(device_scale=0.1)).device_scale, MIN_DEVICE_SCALE)
        self.assertLessEqual(clamp(UserSettings(device_scale=99.0)).device_scale, MAX_DEVICE_SCALE)

    def test_an_unknown_theme_falls_back_rather_than_leaving_a_blank_window(self) -> None:
        self.assertEqual(clamp(UserSettings(theme_mode="chartreuse")).theme_mode, "light")

    def test_an_empty_font_name_falls_back(self) -> None:
        self.assertTrue(clamp(UserSettings(label_font_family="   ")).label_font_family.strip())

    def test_with_changes_clamps_too(self) -> None:
        """The window writes through this, so the box cannot set a nonsense
        value even briefly."""
        self.assertEqual(UserSettings().with_changes(cache_size_limit_mb=0).cache_size_limit_mb, MIN_CACHE_MB)


class RoundTripTests(unittest.TestCase):
    def sample(self) -> UserSettings:
        return UserSettings(
            theme_mode="dark",
            cache_size_limit_mb=2048,
            provider_rps_limit=0.5,
            label_font_family="Helvetica",
            label_font_size=14,
            device_scale=2.0,
        )

    def test_settings_survive_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "settings.json"
            store = SettingsStore(path)
            store.save(self.sample())
            self.assertEqual(store.load(), self.sample())

    def test_a_missing_file_is_a_first_launch_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(SettingsStore(Path(folder) / "none.json").load(), UserSettings())

    def test_a_damaged_file_gives_the_defaults(self) -> None:
        """Losing a preference is a smaller harm than refusing to open."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("{ this is not json", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load(), UserSettings())

    def test_a_file_of_the_wrong_shape_gives_the_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("[1, 2, 3]", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load(), UserSettings())

    def test_an_older_file_costs_only_the_field_it_lacks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(
                json.dumps({"theme_mode": "dark", "cache_size_limit_mb": 100}), encoding="utf-8"
            )
            loaded = SettingsStore(path).load()
            self.assertEqual(loaded.theme_mode, "dark")
            self.assertEqual(loaded.cache_size_limit_mb, 100)
            self.assertEqual(loaded.label_font_family, UserSettings().label_font_family)

    def test_a_hand_edited_nonsense_value_is_clamped_on_the_way_in(self) -> None:
        """The file is meant to be editable. That does not mean trusted."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(
                json.dumps({"cache_size_limit_mb": 0, "provider_rps_limit": -4}), encoding="utf-8"
            )
            loaded = SettingsStore(path).load()
            self.assertGreaterEqual(loaded.cache_size_limit_mb, MIN_CACHE_MB)
            self.assertGreaterEqual(loaded.provider_rps_limit, MIN_RPS)

    def test_a_value_of_the_wrong_type_falls_back_to_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"provider_rps_limit": "quickly"}), encoding="utf-8")
            self.assertEqual(
                SettingsStore(path).load().provider_rps_limit, UserSettings().provider_rps_limit
            )

    def test_the_file_keeps_the_field_names_the_mac_app_uses(self) -> None:
        """The two applications share it."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            SettingsStore(path).save(UserSettings())
            written = set(json.loads(path.read_text(encoding="utf-8")))
            self.assertIn("cache_size_limit_mb", written)
            self.assertIn("provider_rps_limit", written)


class StorageLocationTests(unittest.TestCase):
    def test_every_place_the_app_keeps_something_is_listed(self) -> None:
        from hipparchus.core.config import ConfigLoader

        labels = {label for label, _ in storage_locations(ConfigLoader.load())}
        for expected in ("Preferences", "Saved styles", "Session", "Plugins", "Cache"):
            with self.subTest(place=expected):
                self.assertIn(expected, labels)

    def test_each_one_is_a_path_that_can_be_opened(self) -> None:
        from hipparchus.core.config import ConfigLoader

        for label, path in storage_locations(ConfigLoader.load()):
            with self.subTest(place=label):
                self.assertTrue(str(path))
                self.assertTrue(Path(path).is_absolute())


if __name__ == "__main__":
    unittest.main()


class SplashPreferenceTests(unittest.TestCase):
    """Whether the splash appears at launch is a preference about a window,
    not about how maps are made — but it still has to survive a restart."""

    def test_it_is_shown_by_default(self) -> None:
        """Absent means yes: the first launch is exactly when the attribution
        and the credits are worth reading."""
        self.assertTrue(UserSettings().show_about_on_launch)

    def test_turning_it_off_survives_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            store = SettingsStore(path)
            store.save(UserSettings().with_changes(show_about_on_launch=False))
            self.assertFalse(store.load().show_about_on_launch)

    def test_an_older_file_without_the_field_still_shows_it(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"theme_mode": "dark"}), encoding="utf-8")
            self.assertTrue(SettingsStore(path).load().show_about_on_launch)
