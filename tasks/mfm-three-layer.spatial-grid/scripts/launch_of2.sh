#!/usr/bin/env bash
# of2: the head-to-head against of1 -- the SAME setting (full task from nothing, three-layer on the
# minimal contract, atoms, own scripts and reflexes as the only tick layer, no event sheet, 320x180,
# one compacted thread, 8h wall) with the model swapped: gpt-6-astra at effort MEDIUM on the
# ChatGPT-plan account behind ~/.codex-eval (2026-09-08, the user's ask).
#
# Account plumbing: ~/.codex-eval/auth.json -> ~/.codex/runtime-home/auth.json (account 7631363f).
# Both codex wrappers (~/ccr/bin/codex, ~/.local/bin/codex) relink the arm home's auth.json to
# THEIR account, so this arm calls the codex binary itself; the purple backend sets CODEX_HOME to
# the arm home, where codex-home.sh symlinked MCU_CODEX_AUTH.
set -euo pipefail
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex"
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
export MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json"
FLAGS="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --model gpt-6-astra --reasoning-effort medium --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
TASK=ender_dragon ARM="${ARM:-of2_mfm}" GP="${GP:-9122}" PP="${PP:-9132}" STEPS=100000 SESSION_TURNS=0 COMPACT=1 WALL=8h NO_SEEDS=1 \
  WM_EXTRA="$FLAGS" bash scripts/launch-og.sh
