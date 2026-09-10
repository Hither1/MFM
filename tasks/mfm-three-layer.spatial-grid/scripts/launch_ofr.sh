#!/usr/bin/env bash
# ofNr: the memory-reuse life of ofN (N=1,2,3) -- the SAME setting and model as ofN, seeded with
# ofN's own life alone (EXTRA_ONLY=1 EXTRA_SEEDS=<ofN memory>). The carry is the MFM protocol:
# the harness hard-links the record under previous/life_1/ (logs.txt, episodes/, mine/) and the
# model reads it itself on its workshop turn; no --sites, no --seed-mine (no harness digest, no
# distiller pass). 2026-09-08, the user's word before sleeping: "跑各自的memory reuse，让模型自己处理
# memory而不是用harness处理memory".
#   bash launch_ofr.sh 1   # of1r_mfm  9124/9134  gpt-5.6-sol high, API-key account
#   bash launch_ofr.sh 2   # of2r_mfm  9125/9135  gpt-6-astra medium, nyu plan account
#   bash launch_ofr.sh 3   # of3r_mfm  9126/9136  gpt-6-astra high, nyu plan account
set -euo pipefail
N="${1:?usage: launch_ofr.sh <1|2|3>}"
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
BASE="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
case "$N" in
  1) MODEL="--model gpt-5.6-sol --reasoning-effort high"; GP=9124; PP=9134
     export CODEX_BIN="$HOME/ccr/bin/codex";;
  2) MODEL="--model gpt-6-astra --reasoning-effort medium"; GP=9125; PP=9135
     export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  3) MODEL="--model gpt-6-astra --reasoning-effort high"; GP=9126; PP=9136
     export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  *) echo "N must be 1, 2 or 3" >&2; exit 2;;
esac
SEED="$PWD/output/of${N}_mfm/episode_001/memory"
[ -f "$SEED/logs.txt" ] || { echo "seed $SEED has no logs.txt" >&2; exit 1; }
TASK=ender_dragon ARM="of${N}r_mfm" GP="$GP" PP="$PP" STEPS=100000 SESSION_TURNS=0 COMPACT=1 WALL=8h \
  EXTRA_ONLY=1 EXTRA_SEEDS="$SEED" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
