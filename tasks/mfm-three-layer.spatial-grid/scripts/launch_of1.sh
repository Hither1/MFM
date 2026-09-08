#!/usr/bin/env bash
# of1: the FULL task (ender_dragon) from nothing, gpt-5.6-sol high, the three-layer setting on the
# minimal contract (2026-09-08, the user's decisions in the session of that day):
#   - no seeds (NO_SEEDS=1): no previous lives, no distilled mine/
#   - --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills: the short contract, the 28
#     atoms, the model's own scripts and reflexes as the only tick layer, the meta-level skill package;
#     the reflex examples sit under skills/reflexes/scripts/ and NOTHING is installed under mine/reflexes/
#   - --no-event-sheet: the current view alone, 320x180
#   - one codex thread, compacted at 100k tokens (SESSION_TURNS=0 COMPACT=1)
#   - STEPS=100000 is never the stop; WALL=8h is
# Run from the live checkout; check the launch within two minutes (README-mfm-arms.md, "How to run").
set -euo pipefail
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export CODEX_BIN="$HOME/ccr/bin/codex"
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
FLAGS="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --model gpt-5.6-sol --reasoning-effort high --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
TASK=ender_dragon ARM="${ARM:-of1_mfm}" GP="${GP:-9121}" PP="${PP:-9131}" STEPS=100000 SESSION_TURNS=0 COMPACT=1 WALL=8h NO_SEEDS=1 \
  WM_EXTRA="$FLAGS" bash scripts/launch-og.sh
