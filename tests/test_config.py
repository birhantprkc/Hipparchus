from __future__ import annotations

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
