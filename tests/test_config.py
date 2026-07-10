from __future__ import annotations

import unittest
from unittest import mock

from hipparchus.core.config import ConfigLoader


class ConfigStartOptionsTests(unittest.TestCase):
    def _load_with(self, env: dict[str, str]):
        with mock.patch.dict("os.environ", env, clear=False):
            return ConfigLoader.load()

    def test_defaults_are_off(self) -> None:
        config = self._load_with({"HIPPARCHUS_START_AREA": "", "HIPPARCHUS_FETCH_ON_START": ""})
        self.assertEqual(config.start_area, "")
        self.assertFalse(config.fetch_on_start)

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
