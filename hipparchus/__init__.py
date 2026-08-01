"""Compatibility package for running from source checkout.

This package extends its import path to include ``src/hipparchus`` so
``python -m hipparchus`` works without installing the project.

The version is **read** from the real package rather than restated here. It used
to be a second literal with a comment asking whoever changed one to change the
other — a request nobody can enforce, and it drifted the first time the version
moved, leaving the About window showing a number the project had left behind.
"""

from pathlib import Path
import re

_pkg_dir = Path(__file__).resolve().parent
_src_pkg_dir = _pkg_dir.parent / "src" / "hipparchus"

if _src_pkg_dir.is_dir():
    __path__.append(str(_src_pkg_dir))


def _version_from_source() -> str:
    """The one version, read off the package that declares it."""
    try:
        text = (_src_pkg_dir / "__init__.py").read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - a checkout without src is not usable
        return "0.0.0"
    found = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return found.group(1) if found else "0.0.0"


__version__ = _version_from_source()
