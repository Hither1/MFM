#!/usr/bin/env bash
# Generation 3 of the carry-only chain (plan-gen3.md, user's go required): the lineage's
# gen-2 life is the seed (its previous/ already carries gen 1, so lives_of() gives both),
# SESSION_TURNS=1 (a fresh codex thread every turn: the MFM is the only continuity),
# codex-native skills (.agents/skills), the gen-3 minimal contract (MCU >= 1ac1c7f7).
#   bash launch_g3.sh 3          # of3g_mfm  9128/9138  gpt-6-astra high, seeds of3+of3r
#   bash launch_g3.sh 2          # of2g_mfm  9129/9139  gpt-6-astra medium, seeds of2+of2r
#   bash launch_g3.sh 1          # of1g_mfm  9130/9140  gpt-5.6-sol high (API key), seeds of1+of1r
#   bash launch_g3.sh 3 scratch  # of3s_mfm  9131/9141  the from-scratch control (no seeds), same contract
# Run from MFM-grid/MCU AFTER it is fast-forwarded to the gen-3 MCU commit and no arm is
# running there. WALL=12h by default (WALL env overrides).
set -euo pipefail
N="${1:?usage: launch_g3.sh <1|2|3> [scratch]}"
MODE="${2:-reuse}"
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
BASE="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
case "$N" in
  1) MODEL="--model gpt-5.6-sol --reasoning-effort high"; GP=9130; PP=9140
     export CODEX_BIN="$HOME/ccr/bin/codex";;
  2) MODEL="--model gpt-6-astra --reasoning-effort medium"; GP=9129; PP=9139
     export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  3) MODEL="--model gpt-6-astra --reasoning-effort high"; GP=9128; PP=9138
     export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  *) echo "N must be 1, 2 or 3" >&2; exit 2;;
esac
git -C . merge-base --is-ancestor 1ac1c7f7 HEAD || { echo "MFM-grid/MCU is not at the gen-3 code (needs 1ac1c7f7)" >&2; exit 1; }
if [ "$MODE" = "scratch" ]; then
  TASK=ender_dragon ARM="of${N}s_mfm" GP=$((GP+3)) PP=$((PP+3)) STEPS=100000 SESSION_TURNS=1 WALL="${WALL:-12h}" \
    NO_SEEDS=1 WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
else
  SEED="$PWD/output/of${N}r_mfm/episode_001/memory"
  [ -f "$SEED/logs.txt" ] || { echo "seed $SEED has no logs.txt" >&2; exit 1; }
  [ -d "$SEED/previous/life_1" ] || { echo "seed $SEED carries no life_1 (gen 1 missing)" >&2; exit 1; }
  TASK=ender_dragon ARM="of${N}g_mfm" GP="$GP" PP="$PP" STEPS=100000 SESSION_TURNS=1 WALL="${WALL:-12h}" \
    EXTRA_ONLY=1 EXTRA_SEEDS="$SEED" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
fi
