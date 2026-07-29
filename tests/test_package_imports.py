"""Every subpackage must import cleanly on its own.

A cycle between two packages only fires when one of them is imported first, so
a suite that always reaches the same package first will never see it. This
imports each one in a fresh interpreter, which is the only way to be sure.
"""

from __future__ import annotations

import subprocess
import sys
import unittest

MODULES = (
    "hipparchus",
    "hipparchus.application",
    "hipparchus.cache",
    "hipparchus.core",
    "hipparchus.core.fetch_progress",
    "hipparchus.data_sources",
    "hipparchus.data_sources.data_source_manager",
    "hipparchus.data_sources.terrain_tiles",
    "hipparchus.export",
    "hipparchus.geometry",
    "hipparchus.geometry.bands",
    "hipparchus.geometry.contours",
    "hipparchus.rendering",
    "hipparchus.ui.main_window",
)


class ImportTests(unittest.TestCase):
    def test_each_module_imports_first_in_a_clean_interpreter(self) -> None:
        for name in MODULES:
            with self.subTest(module=name):
                result = subprocess.run(
                    [sys.executable, "-c", f"import {name}"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"importing {name} first failed:\n{result.stderr.strip()[-800:]}",
                )


if __name__ == "__main__":
    unittest.main()
