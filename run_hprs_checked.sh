#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/scripts/python_env.sh"
check_hipparchus_runtime_deps

# The launch-safety subset, not the release gate. This used to call
# `scripts/release_preflight.sh`, which now also enforces Ruff -- and a lint
# finding is no reason to refuse somebody a window. Compile and test only.
"$HIPPARCHUS_PYTHON" -m py_compile $(rg --files -g '*.py')
if "$HIPPARCHUS_PYTHON" -m pytest --version >/dev/null 2>&1; then
  "$HIPPARCHUS_PYTHON" -m pytest
else
  # Pytest lives in the `dev` extra, so a plain install may not have it. This
  # collects fewer cases -- see the note in scripts/release_preflight.sh.
  echo "pytest not installed; falling back to unittest discovery (fewer cases)."
  "$HIPPARCHUS_PYTHON" -m unittest discover -s tests -p 'test_*.py'
fi

echo "Launching Hipparchus GUI..."
if ! "$HIPPARCHUS_PYTHON" -m hipparchus; then
  echo "Hipparchus failed to launch. Re-run with: $HIPPARCHUS_PYTHON -X faulthandler -m hipparchus"
  exit 1
fi
