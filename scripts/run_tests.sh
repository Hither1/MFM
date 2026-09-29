#!/usr/bin/env bash
# Run the offline test suite: no simulator, no container, no model account.
#
#   bash scripts/run_tests.sh                      # the whole suite
#   bash scripts/run_tests.sh tests/test_grid.py -k stall
#
# MFM_PYTHON names the interpreter (default: MCU/.venv/bin/python, else python3). It
# needs the benchmark's own dependencies (numpy, opencv, pillow, pyyaml, loguru, a2a)
# and pytest.
#
# tests/pins_release/ holds what each arm of the paper shows the model and writes beside
# it, byte for byte. A change to a contract, a prompt or a workspace file fails there;
# MFM_RECORD_PINS=1 records the new text when the change is meant.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${MFM_PYTHON:-$ROOT/MCU/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
"$PY" -c "import pytest" 2>/dev/null || { echo "pytest is not installed for $PY" >&2; exit 2; }
[ $# -gt 0 ] || set -- tests/
export PYTHONPATH="$ROOT:$ROOT/CUA-KiCad${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m pytest -q -p no:cacheprovider "$@"
