#!/usr/bin/env bash
# Run the MFM test suite against an MCU checkout.
#
#   bash scripts/run_tests.sh                 # whole suite, MCU = ../MFM-grid-merge-mcu if present, else ./MCU
#   bash scripts/run_tests.sh --core          # the gen-3/4 set only (contract, skills, memory, recall, grid, own)
#   MFM_MCU_ROOT=/path/to/MCU bash scripts/run_tests.sh tests/test_grid.py -k stall
#
# Python: the MCU checkout's .venv (it has the runtime deps; pytest was added 2026-09-09 with
# `uv pip install --python <venv>/bin/python pytest`). The kicad pin tests (test_carry,
# test_pins_*, test_store::*kicad*) import from CUA-KiCad/gym_codex, a plain directory of
# this repo since 2026-09-28; if it is missing they are skipped by tests/conftest.py.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -z "${MFM_MCU_ROOT:-}" ]; then
    if [ -d "$ROOT/../MFM-grid-merge-mcu/mcu_worldmodel" ]; then
        MFM_MCU_ROOT="$(cd "$ROOT/../MFM-grid-merge-mcu" && pwd)"
    else
        MFM_MCU_ROOT="$ROOT/MCU"
    fi
fi
export MFM_MCU_ROOT
PY="$MFM_MCU_ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 2; }
"$PY" -c "import pytest" 2>/dev/null || {
    echo "pytest missing in $MFM_MCU_ROOT/.venv -- install: uv pip install --python $PY pytest" >&2; exit 2; }
[ -d "$ROOT/CUA-KiCad/gym_codex" ] || echo "note: CUA-KiCad/gym_codex missing; the kicad pin tests will be skipped" >&2
CORE=(tests/test_memory_v2.py tests/test_gen4_contract.py tests/test_skills.py tests/test_own_reflex.py
      tests/test_own.py tests/test_retrieve.py tests/test_retrieve_plan.py tests/test_episodes_views.py
      tests/test_grid.py tests/test_previous.py tests/test_thin.py tests/test_watchdog.py)
if [ "${1:-}" = "--core" ]; then
    shift
    set -- "${CORE[@]}" "$@"
elif [ $# -eq 0 ]; then
    set -- tests/
fi
echo "MFM_MCU_ROOT=$MFM_MCU_ROOT  ($(git -C "$MFM_MCU_ROOT" rev-parse --short HEAD 2>/dev/null || echo '?'))  python=$PY"
exec "$PY" -m pytest -q -p no:cacheprovider "$@"
