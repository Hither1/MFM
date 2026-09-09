#!/usr/bin/env bash
# Generation 3 of the carry-only chain (plan-gen3.md, user's go required): the lineage's
# gen-2 life is the seed (its previous/ already carries gen 1, so lives_of() gives both),
# SESSION_TURNS=1 (a fresh codex thread every turn: the MFM is the only continuity),
# codex-native skills (.agents/skills), the gen-3 minimal contract (MCU >= 1ac1c7f7).
#   bash launch_g3.sh 3          # of3g_mfm  9128/9138  gpt-6-astra high, seeds of3+of3r
#   bash launch_g3.sh 2          # of2g_mfm  9129/9139  gpt-6-astra medium, seeds of2+of2r
#   bash launch_g3.sh 1          # of1g_mfm  9130/9140  gpt-5.6-sol high (API key), seeds of1+of1r
#   bash launch_g3.sh 3 scratch  # of3s_mfm  9131/9141  the from-scratch control (no seeds), same contract
#   FRAME_SIZE=320x180 bash launch_g3.sh 3   # the gen-2 frame size instead of the render
# Run from MFM-grid/MCU AFTER it is fast-forwarded to the gen-3 MCU commit and no arm is
# running there. WALL=12h by default (WALL env overrides). SESSION_TURNS default 0 = one thread
# for the life with COMPACT on (codex compacts instead of cold-starting); SESSION_TURNS=1 = a fresh
# codex thread every turn; SESSION_TURNS=10 = a fresh thread every 10 turns.
#   SMOKE=150 bash launch_g3.sh 3          # g3smoke_mfm, 150 steps, ports 9127/9137, WALL 30m
# ACCOUNT=openrouter|api|nyu picks the account (default openrouter, user's decision 2026-09-09):
#   openrouter: scripts/codex-openrouter.sh (the raw binary through the host's proxy; OpenRouter
#               geo-gates this host) on the backend's --base-url path, model ids `openai/<id>`, the
#               key obtained by codex itself from the 600 file named in MCU_OPENROUTER_ENV
#               (CODEX_LOCAL_AUTH_COMMAND -> auth.command, never in any environment), no auth.json,
#               context window 1,050,000 (OpenRouter's figure for the gpt-6 / gpt-5.6 ids).
#   api:        $HOME/ccr/bin/codex (the OpenAI API-key wrapper).
#   nyu:        the raw binary + MCU_CODEX_AUTH = the ChatGPT-plan auth.json.
set -euo pipefail
N="${1:?usage: launch_g3.sh <1|2|3> [scratch]}"
MODE="${2:-reuse}"
# SESSION_TURNS=0 (user's decision 2026-09-09): one codex thread for the whole life, compacted by
# codex at 100k tokens (COMPACT=1 follows). SESSION_TURNS=1 = a fresh thread every turn.
ST="${SESSION_TURNS:-0}"
CM=0; [ "$ST" = "0" ] && CM=1
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
# FRAME_SIZE: WxH of the frames the model is shown. 640x360 = the render (user's decision
# 2026-09-09 after the read-out: at 320x180 the model cannot read the hotbar; +216 tokens per
# frame). The full-resolution record under episode_001/hires/ is kept regardless (--hires-every,
# default every step) and the model is never told about it.
BASE="--expect --frames --retrieval --no-event-sheet --frame-size ${FRAME_SIZE:-640x360} --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
ACC="${ACCOUNT:-openrouter}"
case "$N" in
  1) MID=gpt-5.6-sol; EFF=high; GP=9130; PP=9140;;
  2) MID=gpt-6-astra; EFF=medium; GP=9129; PP=9139;;
  3) MID=gpt-6-astra; EFF=high; GP=9128; PP=9138;;
  *) echo "N must be 1, 2 or 3" >&2; exit 2;;
esac
MODEL="--model $MID --reasoning-effort $EFF"
case "$ACC" in
  openrouter)
    KEYFILE="${MCU_OPENROUTER_ENV:-/datapool/data3/storage/ruihan/data_share/jh/Collab/secrets/openrouter.env}"
    [ -r "$KEYFILE" ] || { echo "no readable OpenRouter key file at $KEYFILE (MCU_OPENROUTER_ENV)" >&2; exit 1; }
    export CODEX_BIN="$PWD/scripts/codex-openrouter.sh" MCU_CODEX_AUTH=none
    export CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
    export CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-1050000}"
    MODEL="--model openai/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api/v1";;
  api) export CODEX_BIN="$HOME/ccr/bin/codex"; unset MCU_CODEX_AUTH;;
  nyu) export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  *) echo "ACCOUNT must be openrouter, api or nyu" >&2; exit 2;;
esac
echo "account=$ACC codex=$CODEX_BIN${MCU_CODEX_AUTH:+ auth=$MCU_CODEX_AUTH} model: $MODEL frames: ${FRAME_SIZE:-640x360}"
git -C . merge-base --is-ancestor 1ac1c7f7 HEAD || { echo "MFM-grid/MCU is not at the gen-3 code (needs 1ac1c7f7)" >&2; exit 1; }
# SMOKE=<steps>: the same arm as a short smoke -- arm g3smoke_mfm, ports 9127/9137, WALL 30m.
STEPS=100000; ARM_OVERRIDE=""
if [ -n "${SMOKE:-}" ]; then STEPS="$SMOKE"; ARM_OVERRIDE=g3smoke_mfm; GP=9127; PP=9137; WALL="${WALL:-30m}"; fi
if [ "$MODE" = "scratch" ]; then
  TASK=ender_dragon ARM="${ARM_OVERRIDE:-of${N}s_mfm}" GP=$((GP+3)) PP=$((PP+3)) STEPS="$STEPS" SESSION_TURNS="$ST" COMPACT="$CM" WALL="${WALL:-12h}" \
    NO_SEEDS=1 WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
else
  SEED="$PWD/output/of${N}r_mfm/episode_001/memory"
  [ -f "$SEED/logs.txt" ] || { echo "seed $SEED has no logs.txt" >&2; exit 1; }
  [ -d "$SEED/previous/life_1" ] || { echo "seed $SEED carries no life_1 (gen 1 missing)" >&2; exit 1; }
  TASK=ender_dragon ARM="${ARM_OVERRIDE:-of${N}g_mfm}" GP="$GP" PP="$PP" STEPS="$STEPS" SESSION_TURNS="$ST" COMPACT="$CM" WALL="${WALL:-12h}" \
    EXTRA_ONLY=1 EXTRA_SEEDS="$SEED" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
fi
