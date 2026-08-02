"""One version, in one place.

There are two importable `hipparchus` packages in a source checkout — the real
one under `src/`, and a shim at the root so `python -m hipparchus` works without
installing. The shim used to restate the version with a comment asking whoever
changed one to change the other. That is a request nobody can enforce, and it
drifted the first time the version moved: the About window went on showing a
number the project had left behind.

`pyproject.toml` is a third place the number appears, and it is what anybody
installing this gets.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def declared_in(path: Path, pattern: str) -> str:
    found = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert found is not None, f"no version found in {path}"
    return found.group(1)


class VersionTests(unittest.TestCase):
    def test_the_package_declares_a_version(self) -> None:
        from hipparchus import __version__

        self.assertRegex(__version__, r"^\d+\.\d+\.\d+")

    def test_the_shim_reports_the_same_version_as_the_package(self) -> None:
        """Whichever of the two a caller happens to import."""
        source = declared_in(
            ROOT / "src" / "hipparchus" / "__init__.py", r'^__version__\s*=\s*"([^"]+)"'
        )
        shim = ROOT / "hipparchus" / "__init__.py"
        self.assertNotRegex(
            shim.read_text(encoding="utf-8"),
            r'^__version__\s*=\s*"\d',
            "the shim states a version of its own instead of reading one",
        )

        import importlib

        import hipparchus

        importlib.reload(hipparchus)
        self.assertEqual(hipparchus.__version__, source)

    def test_the_packaging_metadata_agrees(self) -> None:
        """What anybody installing this actually gets."""
        source = declared_in(
            ROOT / "src" / "hipparchus" / "__init__.py", r'^__version__\s*=\s*"([^"]+)"'
        )
        packaged = declared_in(ROOT / "pyproject.toml", r'^version\s*=\s*"([^"]+)"')
        self.assertEqual(packaged, source)

    def test_the_about_window_shows_the_same_version(self) -> None:
        from hipparchus import __version__
        from hipparchus.application.about import about

        self.assertEqual(about().version, __version__)

    def test_the_changelog_has_an_entry_for_it(self) -> None:
        """A version nobody wrote down is a version nobody can tell apart from
        the one before it."""
        from hipparchus import __version__

        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {__version__}", changelog)


if __name__ == "__main__":
    unittest.main()
