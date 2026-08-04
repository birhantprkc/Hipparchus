from __future__ import annotations

import os
import unittest
from unittest import mock

from hipparchus.core.config import ConfigLoader


class ConfigStartOptionsTests(unittest.TestCase):
    def _load_with(self, env: dict[str, str]):
        with mock.patch.dict("os.environ", env, clear=False):
            return ConfigLoader.load()

    def test_defaults_are_off(self) -> None:
        config = self._load_with(
            {"HIPPARCHUS_START_AREA": "", "HIPPARCHUS_FETCH_ON_START": "", "HIPPARCHUS_START_PRESET": ""}
        )
        self.assertEqual(config.start_area, "")
        self.assertFalse(config.fetch_on_start)
        self.assertEqual(config.start_preset, "")

    def test_start_preset_is_read_and_stripped(self) -> None:
        config = self._load_with({"HIPPARCHUS_START_PRESET": "  Night  "})
        self.assertEqual(config.start_preset, "Night")

    def test_start_area_is_read_and_stripped(self) -> None:
        config = self._load_with({"HIPPARCHUS_START_AREA": "  Venice Historic  "})
        self.assertEqual(config.start_area, "Venice Historic")

    def test_fetch_on_start_truthy_values(self) -> None:
        for value in ("1", "true", "TRUE", "yes", "On"):
            with self.subTest(value=value):
                config = self._load_with({"HIPPARCHUS_FETCH_ON_START": value})
                self.assertTrue(config.fetch_on_start)

    def test_fetch_on_start_falsy_values(self) -> None:
        for value in ("", "0", "false", "no", "off", "maybe"):
            with self.subTest(value=value):
                config = self._load_with({"HIPPARCHUS_FETCH_ON_START": value})
                self.assertFalse(config.fetch_on_start)


if __name__ == "__main__":
    unittest.main()


class StartSourcesTests(unittest.TestCase):
    """A launch can be told what the map is made of, not just where it is."""

    def _load(self, value: str | None):
        import os
        from hipparchus.core.config import ConfigLoader

        previous = os.environ.get("HIPPARCHUS_START_SOURCES")
        if value is None:
            os.environ.pop("HIPPARCHUS_START_SOURCES", None)
        else:
            os.environ["HIPPARCHUS_START_SOURCES"] = value
        try:
            return ConfigLoader.load()
        finally:
            if previous is None:
                os.environ.pop("HIPPARCHUS_START_SOURCES", None)
            else:
                os.environ["HIPPARCHUS_START_SOURCES"] = previous

    def test_unset_means_the_defaults_apply(self) -> None:
        self.assertEqual(self._load(None).start_sources, ())

    def test_a_comma_separated_list_is_parsed(self) -> None:
        self.assertEqual(
            self._load("overpass, terrain_tiles").start_sources,
            ("overpass", "terrain_tiles"),
        )

    def test_blank_entries_are_dropped(self) -> None:
        self.assertEqual(self._load(" , terrain_tiles ,, ").start_sources, ("terrain_tiles",))


class AppIconTests(unittest.TestCase):
    """The window/taskbar icon, ported from the Mac's own AppIcon."""

    def _load_with(self, env: dict[str, str]):
        with mock.patch.dict("os.environ", env, clear=False):
            return ConfigLoader.load()

    def test_the_packaged_default_is_a_real_file(self) -> None:
        config = self._load_with({"HIPPARCHUS_APP_ICON": ""})
        self.assertTrue(os.path.isfile(config.app_icon))
        self.assertTrue(config.app_icon.endswith(".png"))

    def test_the_environment_can_override_it(self) -> None:
        config = self._load_with({"HIPPARCHUS_APP_ICON": "/tmp/some-other-icon.png"})
        self.assertEqual(config.app_icon, "/tmp/some-other-icon.png")


class WindowSizeTests(unittest.TestCase):
    """How big the window opens, and how small it may be dragged.

    It opened 1600x1080 with a minimum of 1400x980 — larger than a 13-inch
    laptop's whole screen, and unshrinkable below it. The macOS application
    opens 1100x800 with a minimum of 960x620, and that is the pair to match.
    """

    def setUp(self) -> None:
        self._previous = {
            key: os.environ.pop(key, None)
            for key in ("HIPPARCHUS_WINDOW_WIDTH", "HIPPARCHUS_WINDOW_HEIGHT")
        }

    def tearDown(self) -> None:
        for key, value in self._previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_it_opens_at_the_size_the_mac_opens_at(self) -> None:
        config = ConfigLoader.load()
        self.assertEqual((config.default_width, config.default_height), (1100, 800))

    def test_the_minimum_is_the_one_the_mac_uses(self) -> None:
        config = ConfigLoader.load()
        self.assertEqual((config.min_width, config.min_height), (960, 620))

    def test_it_fits_on_a_laptop(self) -> None:
        """A 13-inch MacBook is 1440x900 of usable space. A window that opens
        larger than the screen, and refuses to shrink, cannot be used at all."""
        config = ConfigLoader.load()
        self.assertLessEqual(config.default_width, 1440)
        self.assertLessEqual(config.default_height, 900)
        self.assertLessEqual(config.min_width, 1440)
        self.assertLessEqual(config.min_height, 900)

    def test_the_environment_can_ask_for_another_size(self) -> None:
        os.environ["HIPPARCHUS_WINDOW_WIDTH"] = "1680"
        os.environ["HIPPARCHUS_WINDOW_HEIGHT"] = "1000"
        config = ConfigLoader.load()
        self.assertEqual((config.default_width, config.default_height), (1680, 1000))

    def test_the_minimum_never_exceeds_the_size_asked_for(self) -> None:
        """Otherwise the window opens at the minimum instead of the size that
        was requested, and the request looks ignored."""
        os.environ["HIPPARCHUS_WINDOW_WIDTH"] = "800"
        os.environ["HIPPARCHUS_WINDOW_HEIGHT"] = "560"
        config = ConfigLoader.load()
        self.assertLessEqual(config.min_width, config.default_width)
        self.assertLessEqual(config.min_height, config.default_height)

    def test_a_nonsense_size_falls_back_rather_than_failing_to_start(self) -> None:
        os.environ["HIPPARCHUS_WINDOW_WIDTH"] = "wide"
        os.environ["HIPPARCHUS_WINDOW_HEIGHT"] = ""
        config = ConfigLoader.load()
        self.assertEqual((config.default_width, config.default_height), (1100, 800))
