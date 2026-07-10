#!/usr/bin/env zsh
# One-command dependency setup for Hipparchus (macOS / Linux).
#
# Installs the Python packages Hipparchus needs into your normal Python.
# No virtual environment is created. Run this once after cloning:
#
#   ./setup.sh          # core runtime (numpy, scipy, shapely, skia-python)
#   ./setup.sh --maps   # also install optional local map-source backends
#
# Then launch with: ./run_hprs.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Reuse the shared interpreter detection + Python 3.11+ version check.
source "$SCRIPT_DIR/scripts/python_env.sh"

runtime_packages=(numpy scipy shapely skia-python)
maps_packages=(fiona mapbox-vector-tile osmium pmtiles pyarrow rasterio scikit-image)

packages=("${runtime_packages[@]}")
if [[ "${1:-}" == "--maps" ]]; then
  packages+=("${maps_packages[@]}")
fi

echo "Hipparchus setup"
echo "  Python: $HIPPARCHUS_PYTHON (version $PYTHON_VERSION)"
echo "  Installing: ${packages[*]}"
echo ""

# Try a --user install first (works for python.org / most system Pythons),
# then fall back to a plain install (needed for conda/base environments).
if "$HIPPARCHUS_PYTHON" -m pip install --user "${packages[@]}"; then
  :
elif "$HIPPARCHUS_PYTHON" -m pip install "${packages[@]}"; then
  :
else
  echo "" >&2
  echo "Dependency install failed." >&2
  echo "If you saw an 'externally-managed-environment' (PEP 668) error, pick one:" >&2
  echo "  - Install into a virtual environment you manage, or" >&2
  echo "  - Re-run pip with --break-system-packages, or" >&2
  echo "  - Use your OS package manager / conda for these packages." >&2
  exit 1
fi

# tkinter ships with Python and cannot be installed with pip.
if ! "$HIPPARCHUS_PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
  echo "" >&2
  echo "Warning: tkinter is missing from this Python and cannot be installed with pip." >&2
  case "$(uname -s)" in
    Linux)  echo "  Install it with your package manager, e.g.: sudo apt install python3-tk" >&2 ;;
    Darwin) echo "  Use a Tk-enabled Python (python.org installer, or: brew install python-tk)." >&2 ;;
    *)      echo "  Install the Tcl/Tk support package for your Python distribution." >&2 ;;
  esac
  echo "  Hipparchus needs tkinter to open its window." >&2
fi

echo ""
echo "Setup complete. Launch Hipparchus with:  ./run_hprs.sh"
