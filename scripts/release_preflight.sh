#!/usr/bin/env zsh
set -euo pipefail

# The gate for publishing a change: compile, lint, the full test inventory, and
# the runtime dependencies. It is deliberately stricter than what it takes to
# launch the app -- `run_hprs_checked.sh` runs the launch-safety subset instead,
# so a lint finding never stands between somebody and a running window.

cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"
source "$SCRIPT_DIR/scripts/python_env.sh"

"$HIPPARCHUS_PYTHON" -m py_compile $(rg --files -g '*.py')

# Ruff is declared in the `dev` extra and documented, but until now nothing ran
# it, which is how ten findings accumulated unnoticed. Missing is a hard failure
# here: a release gate that silently skips its own lint check is not a gate.
if ! "$HIPPARCHUS_PYTHON" -m ruff --version >/dev/null 2>&1; then
  echo "Ruff is not installed for $HIPPARCHUS_PYTHON." >&2
  echo "Install the development extras:" >&2
  echo "  $HIPPARCHUS_PYTHON -m pip install --user 'ruff>=0.1.0'" >&2
  exit 1
fi
"$HIPPARCHUS_PYTHON" -m ruff check .

# Pytest, not `unittest discover`. The two do not collect the same inventory --
# 1,506 cases against 1,471 at 0.7.0 -- and pytest is the runner the README
# documents, so a green preflight now means the documented suite is green.
if ! "$HIPPARCHUS_PYTHON" -m pytest --version >/dev/null 2>&1; then
  echo "Pytest is not installed for $HIPPARCHUS_PYTHON." >&2
  echo "Install the development extras:" >&2
  echo "  $HIPPARCHUS_PYTHON -m pip install --user 'pytest>=7.0' 'Pillow>=10.0'" >&2
  exit 1
fi
"$HIPPARCHUS_PYTHON" -m pytest

"$HIPPARCHUS_PYTHON" -c "import importlib.util as u; assert u.find_spec('shapely'); print('shapely OK')"
"$HIPPARCHUS_PYTHON" -c "import importlib.util as u; print('skia present:', bool(u.find_spec('skia')))"

echo "Preflight checks passed"
