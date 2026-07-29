"""Compatibility package for running from source checkout.

This package extends its import path to include ``src/hipparchus`` so
``python -m hipparchus`` works without installing the project.
"""

from pathlib import Path

# Keep in sync with src/hipparchus/__init__.py.
__version__ = "0.3.2"

_pkg_dir = Path(__file__).resolve().parent
_src_pkg_dir = _pkg_dir.parent / "src" / "hipparchus"

if _src_pkg_dir.is_dir():
    __path__.append(str(_src_pkg_dir))
