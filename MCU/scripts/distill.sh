#!/usr/bin/env bash
# The distiller pass between two lives (mcu_worldmodel/distill.py): one codex run over the
# seeds' records that writes mine/GUIDE.md, the scripts worth keeping, candidate reflexes
# and a frame index. Then launch the next life with WM_EXTRA="... --seed-mine <OUT>/memory/mine".
#   MFM_ROOT=/abs/MFM-grid scripts/distill.sh og23_distill output/og23_distill <life>/episode_001/memory [...]
#   MODEL=gpt-5.6-sol EFFORT=xhigh MINUTES=40 are the defaults.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?usage: distill.sh <name> <out-dir> <seed-memory>...}"; OUT="${2:?out dir}"; shift 2
[ $# -ge 1 ] || { echo "at least one seed memory dir" >&2; exit 1; }
eval "$(scripts/codex-home.sh "$NAME")"
# The ChatGPT-plan login, as run-arm.sh and codex-home.sh use: ~/ccr/bin/codex does not
# exist on this host, and a missing CODEX_BIN does not fail loudly -- the adapter swallows
# the FileNotFoundError, so the pass would run its length and distil nothing.
export CODEX_BIN="${CODEX_BIN:-codex}"
ROOT="$(pwd)"
MFM_DEFAULT="$ROOT/.."; [ -d "$ROOT/../MFM-grid/mfm" ] && MFM_DEFAULT="$ROOT/../MFM-grid"
export PYTHONPATH="${MFM_ROOT:-$MFM_DEFAULT}${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
SEEDS=(); for d in "$@"; do [ -d "$d" ] || { echo "missing seed $d" >&2; exit 1; }; SEEDS+=(--seed-memory "$d"); done
mkdir -p logs
exec .venv/bin/python scripts/distill.py --out "$OUT" --codex-home "$CODEX_RUNTIME_HOME" \
    --model "${MODEL:-gpt-5.6-sol}" --reasoning-effort "${EFFORT:-xhigh}" --minutes "${MINUTES:-40}" \
    "${SEEDS[@]}"
