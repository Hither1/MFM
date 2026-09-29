#!/usr/bin/env bash
# The spatial-grid half-task arms (harness: grid, map-aware go_to / pose re-open / pond
# escape, watchdog, [RECENT]/[MAP], event sheet; mfm options: --expect --frames
# --retrieval). Memory reuse is the MFM carry ONLY: the seeds' records are linked under
# previous/ for the model to read; no --sites (the harness digest of earlier lives that
# the ob1..obf3 chain of 2026-09-06 ran with -- those lives are excluded as seeds for the
# same reason: every plan in their logs was written from the pushed coordinates).
# Seeds: the 12 first-generation lives (worldmodel/logbook arms, never seeded) + the
# spatial-grid lives run without pushed sites (GRID_SEEDS, default og3_mfm og4_mfm).
# Detached; pid in logs/<ARM>_launch.pid.
#   ARM=og5_mfm GP=9095 PP=9105 bash scripts/launch-og.sh
#   ARM=og6_mfm GP=9096 PP=9106 SESSION_TURNS=8 WM_EXTRA="--expect --frames --retrieval --frame-size 320x180" bash scripts/launch-og.sh
#   COMPACT=1 lets codex compact instead of cold-starting; WALL=10h stops the arm at that wall-clock time.
#   NO_SEEDS=1 runs from scratch (no previous lives at all).
#   TASK=ender_dragon runs the full task from nothing (default ender_dragon_half).
#   EXTRA_ONLY=1 EXTRA_SEEDS="/abs/.../episode_001/memory ..." seeds with those lives alone.
#   OB_SEEDS=1 adds the ob1..obf3 lives (contaminated: only with WM_EXTRA containing --sites, to reproduce that arm).
set -euo pipefail
cd "$(dirname "$0")/.."
ARM="${ARM:-og5_mfm}"
GP="${GP:-9095}"; PP="${PP:-9105}"
OLD=/datapool/data3/storage/ruihan/data_share/jh/Collab/MCU-AgentBeats/output
NEW=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM/MCU/output
SEEDS=""
for a in hd12z_wm_high hd32z_wm_high hd39z_wm_high hd43z_wm_high hd41z_wm_high kd35z_lb_high \
         dm16_wm_high dm17_wm_high kd14x_wm_high kd31z_lb_high kd6_wm_high kdc3z_logbook_high; do
    [ -d "$OLD/$a/episode_001/memory" ] || { echo "missing seed $OLD/$a" >&2; exit 1; }
    SEEDS="$SEEDS --seed-memory $OLD/$a/episode_001/memory"
done
# The spatial-grid lives that ran WITHOUT pushed sites (clean carry material), oldest first.
GRID=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output
for a in ${GRID_SEEDS:-og3_mfm og4_mfm}; do
    [ -d "$GRID/$a/episode_001/memory" ] && SEEDS="$SEEDS --seed-memory $GRID/$a/episode_001/memory"
done
# EXTRA_SEEDS: memory dirs by absolute path (lives kept outside MFM-grid/MCU/output).
for d in ${EXTRA_SEEDS:-}; do
    [ -d "$d" ] && SEEDS="$SEEDS --seed-memory $d"
done
if [ "${OB_SEEDS:-0}" = "1" ]; then
    for a in ob1_mfm ob1b_mfm ob2_mfm ob3_mfm ob4_mfm ob5_mfm ob6_mfm obf1_mfm obf2_mfm obf3_mfm; do
        [ -d "$NEW/$a/episode_001/memory" ] && SEEDS="$SEEDS --seed-memory $NEW/$a/episode_001/memory"
    done
fi
# NO_SEEDS=1: from scratch -- no previous lives at all (the new-settings baseline, 2026-09-07).
if [ "${NO_SEEDS:-0}" = "1" ]; then
    SEEDS=""
fi
# EXTRA_ONLY=1: the seeds are EXTRA_SEEDS alone -- a chain seeded with specific lives and
# nothing else (og15 = og14's own life, the self-harness across-lives claim, 2026-09-07).
if [ "${EXTRA_ONLY:-0}" = "1" ]; then
    SEEDS=""
    for d in ${EXTRA_SEEDS:-}; do
        [ -d "$d" ] || { echo "missing seed $d" >&2; exit 1; }
        SEEDS="$SEEDS --seed-memory $d"
    done
    [ -n "$SEEDS" ] || { echo "EXTRA_ONLY=1 needs EXTRA_SEEDS" >&2; exit 1; }
fi
export CODEX_BIN="${CODEX_BIN:-$HOME/ccr/bin/codex}"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
mkdir -p logs
setsid nohup bash scripts/run-arm.sh --arm "$ARM" --agent "${AGENT:-mfm}" --cli "${CLI:-codex}" --task "${TASK:-ender_dragon_half}" \
    --steps "${STEPS:-12000}" --green-port "$GP" --purple-port "$PP" \
    --session-turns "${SESSION_TURNS:-1}" $([ "${COMPACT:-0}" = "1" ] && echo --compact) \
    --wm-extra "${WM_EXTRA:---expect --frames --retrieval}" $SEEDS ${SEED_LOG:+--seed-log "$SEED_LOG"} \
    > "logs/${ARM}_launch.log" 2>&1 < /dev/null &
echo $! > "logs/${ARM}_launch.pid"
echo "launched $ARM (pid $(cat logs/${ARM}_launch.pid)); logs/${ARM}_launch.log"
# WALL: the wall-clock cap. At that time the arm's tree is stopped by pid (stop_arm.py),
# whatever step it is on; the workspace log and milestones up to then stand.
if [ -n "${WALL:-}" ]; then
    setsid nohup bash -c "sleep $WALL; .venv/bin/python scripts/stop_arm.py --go $ARM" \
        > "logs/${ARM}_wall.log" 2>&1 < /dev/null &
    echo $! > "logs/${ARM}_wall.pid"
    echo "wall-clock cap $WALL (watchdog pid $(cat logs/${ARM}_wall.pid))"
fi
