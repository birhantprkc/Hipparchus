#!/usr/bin/env zsh
# Shared Python launcher setup for running Hipparchus from a source checkout.

if [[ -z "${SCRIPT_DIR:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi

# Score one interpreter: 2 = 3.11+ with the runtime dependencies installed,
# 1 = 3.11+ but missing some of them, 0 = unusable. One process per candidate.
_hipparchus_python_score() {
  "$1" -c 'import sys
if sys.version_info < (3, 11):
    raise SystemExit(0)
import importlib.util as u
ready = all(u.find_spec(m) for m in ("numpy", "scipy", "shapely"))
print(2 if ready else 1)' 2>/dev/null || true
}

_hipparchus_python_version() {
  "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || true
}

if [[ -n "${HIPPARCHUS_PYTHON:-}" ]]; then
  # Explicitly chosen, so it is not this script's place to substitute another.
  # Say exactly what is wrong with the one that was asked for and stop.
  if ! command -v "$HIPPARCHUS_PYTHON" >/dev/null 2>&1; then
    echo "Python interpreter not found: $HIPPARCHUS_PYTHON" >&2
    echo "Set HIPPARCHUS_PYTHON to a Python 3.11+ executable, for example:" >&2
    echo "  HIPPARCHUS_PYTHON=/opt/homebrew/bin/python3 ./run_hprs.sh" >&2
    exit 1
  fi
  if [[ "$(_hipparchus_python_score "$HIPPARCHUS_PYTHON")" == "" ]]; then
    echo "Hipparchus needs Python 3.11 or newer. Found Python $(_hipparchus_python_version "$HIPPARCHUS_PYTHON") at: $HIPPARCHUS_PYTHON" >&2
    exit 1
  fi
else
  # Nothing chosen, so look for something that works rather than insisting on
  # whatever `python3` happens to mean. On macOS it frequently means Xcode's
  # 3.10, which is below the floor -- while a perfectly good 3.12 with every
  # dependency installed sits on the same disk. Failing in that situation is
  # a wrong answer the machine had enough information to avoid.
  #
  # Newest first within each source, and an interpreter that can already import
  # the runtime dependencies beats a newer bare one: the point is to find the
  # environment Hipparchus actually runs in, not the highest version number.
  _hipparchus_candidates=(
    python3.14 python3.13 python3.12 python3.11 python3
    /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11
    /usr/local/bin/python3.14 /usr/local/bin/python3.13
    /usr/local/bin/python3.12 /usr/local/bin/python3.11
    "$HOME/miniconda3/bin/python3" "$HOME/miniforge3/bin/python3"
    "$HOME/anaconda3/bin/python3"
  )

  _hipparchus_best=""
  _hipparchus_best_score=0
  _hipparchus_seen=""
  for _hipparchus_candidate in "${_hipparchus_candidates[@]}"; do
    command -v "$_hipparchus_candidate" >/dev/null 2>&1 || continue
    _hipparchus_resolved="$(command -v "$_hipparchus_candidate")"
    # Most of these names are symlinks to each other; probe each one once.
    case " $_hipparchus_seen " in
      *" $_hipparchus_resolved "*) continue ;;
    esac
    _hipparchus_seen="$_hipparchus_seen $_hipparchus_resolved"

    # Written as plain `if`s rather than `&&` lists: the callers run with
    # `set -e`, where a trailing `test && continue` that simply does not fire
    # takes the whole script down with it.
    _hipparchus_score="$(_hipparchus_python_score "$_hipparchus_candidate")"
    if [[ -z "$_hipparchus_score" ]]; then
      continue
    fi
    if (( _hipparchus_score > _hipparchus_best_score )); then
      _hipparchus_best="$_hipparchus_candidate"
      _hipparchus_best_score=$_hipparchus_score
    fi
    if (( _hipparchus_best_score == 2 )); then
      break
    fi
  done

  if [[ -z "$_hipparchus_best" ]]; then
    echo "Hipparchus needs Python 3.11 or newer, and none was found." >&2
    echo "Tried: $_hipparchus_candidates" >&2
    echo "Set HIPPARCHUS_PYTHON to a Python 3.11+ executable, for example:" >&2
    echo "  HIPPARCHUS_PYTHON=/opt/homebrew/bin/python3 ./run_hprs.sh" >&2
    exit 1
  fi

  export HIPPARCHUS_PYTHON="$_hipparchus_best"
  # Only worth a line when it is not the obvious one, so the usual case stays
  # quiet and the surprising case is never silent.
  if [[ "$_hipparchus_best" != "python3" ]]; then
    echo "Using Python $(_hipparchus_python_version "$_hipparchus_best") at: $(command -v "$_hipparchus_best")" >&2
  fi
fi

export HIPPARCHUS_PYTHON

# `setup.sh` prints this, and runs under `set -u` where leaving it unset is a
# hard error rather than a blank in a banner.
PYTHON_VERSION="$(_hipparchus_python_version "$HIPPARCHUS_PYTHON")"
export PYTHON_VERSION

# This file is sourced, so the search scratch would otherwise stay in the
# caller's shell for the rest of the run.
unset _hipparchus_candidates _hipparchus_candidate _hipparchus_resolved \
      _hipparchus_seen _hipparchus_score _hipparchus_best _hipparchus_best_score \
      2>/dev/null || true

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="$SCRIPT_DIR/src:$SCRIPT_DIR:$PYTHONPATH"
else
  export PYTHONPATH="$SCRIPT_DIR/src:$SCRIPT_DIR"
fi

check_hipparchus_runtime_deps() {
  "$HIPPARCHUS_PYTHON" - <<'PY'
import importlib.util
import sys

required = {
    "numpy": "numpy",
    "scipy": "scipy",
    "shapely": "shapely",
    "tkinter": "tkinter",
}
missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
if missing:
    print("Missing required Python packages:", ", ".join(missing), file=sys.stderr)
    print("", file=sys.stderr)
    print("Run the one-command setup from the repository root:", file=sys.stderr)
    print("  ./setup.sh", file=sys.stderr)
    print("", file=sys.stderr)
    print("Or install them manually into your normal Python:", file=sys.stderr)
    print(f"  {sys.executable} -m pip install --user numpy scipy shapely", file=sys.stderr)
    raise SystemExit(1)

if importlib.util.find_spec("skia") is None:
    print("Warning: skia-python is not installed; Hipparchus will use the fallback renderer.", file=sys.stderr)
    print(f"Install it with: {sys.executable} -m pip install --user skia-python", file=sys.stderr)
PY
}
