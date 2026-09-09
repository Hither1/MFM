#!/usr/bin/env bash
# Generation 4 (2026-09-10): the head-to-head of two settings, both seeded with of3r (16/24,
# gen 2; its previous/ already carries of3, so the workshop sees both lives). Plan and
# rationale: tasks/mfm-three-layer.spatial-grid/analysis/gen4_plan_2026-09-10.md (sections 8, 11).
#   bash launch_g4.sh min    # of3m_mfm 9133/9143: gen 2 exactly + the three edits (MFM-grid-min-mcu,
#                            #   branch gen4-min), frames 320x180 as of3r had them
#   bash launch_g4.sh full   # of3f_mfm 9132/9142: gen 2 + gen 3's neutral fixes + the three edits, none
#                            #   of gen 3's doctrine (MFM-grid-merge-mcu, branch gen4-full), frames 640x360
#   SMOKE=150 bash launch_g4.sh min|full   # g4smoke_<arm>_mfm, 150 steps, ports 9127/9137 (min) or
#                            #   9126/9136 (full), WALL 30m: one workshop turn + a plan or two
# Both arms: gpt-6-astra high through OpenRouter (ACCOUNT=openrouter default; api|nyu as in
# launch_g3.sh), one codex thread for the life compacted by codex (SESSION_TURNS=0, COMPACT=1),
# STEPS=100000, WALL 14h (WALL env overrides), TASK=ender_dragon, carry-only seeding
# (EXTRA_ONLY=1, no --sites). FRAME_SIZE overrides the arm's default.
# The three model-facing edits shared by both arms (analysis/gen4_contract_diff_{min,full}.txt):
# the starving example eats what you carry when the bar drops below 18, the hunger line in
# Safety, then-now on arrival at a remembered place + the episode id beside each digest place.
set -euo pipefail
ARM_KIND="${1:?usage: launch_g4.sh <min|full>}"
C=/datapool/data3/storage/ruihan/data_share/jh/Collab
case "$ARM_KIND" in
  min)  MCU="$C/MFM-grid-min-mcu";   export MFM_ROOT="$C/MFM-grid-min"; ARM=of3m_mfm; GP=9133; PP=9143; FS="${FRAME_SIZE:-320x180}"; NEED=bfd31b31; SGP=9127; SPP=9137;;
  full) MCU="$C/MFM-grid-merge-mcu"; export MFM_ROOT="$C/MFM-grid";     ARM=of3f_mfm; GP=9132; PP=9142; FS="${FRAME_SIZE:-640x360}"; NEED=a7dbe7ba; SGP=9126; SPP=9136;;
  *) echo "arm must be min or full" >&2; exit 2;;
esac
cd "$MCU"
git -C . merge-base --is-ancestor "$NEED" HEAD || { echo "$MCU is not at the gen-4 $ARM_KIND code (needs $NEED)" >&2; exit 1; }
[ -z "$(git -C . status --porcelain -- mcu_worldmodel scripts)" ] || { echo "$MCU has uncommitted changes under mcu_worldmodel/ or scripts/" >&2; exit 1; }
export MCU_CODEX_ROOT="$C/codex-homes"
# The launching shell may carry http_proxy/https_proxy (the host reaches OpenRouter through one);
# the harness talks to its own servers on 127.0.0.1 with urllib/httpx, which honour those unless
# loopback is excluded -- without this the readiness check reads "still starting" against a
# server that is up (2026-09-10 smoke).
export no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}" NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"
ST="${SESSION_TURNS:-0}"; CM=0; [ "$ST" = "0" ] && CM=1
BASE="--expect --frames --retrieval --no-event-sheet --frame-size $FS --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
MID=gpt-6-astra; EFF=high
MODEL="--model $MID --reasoning-effort $EFF"
case "${ACCOUNT:-openrouter}" in
  openrouter)
    KEYFILE="${MCU_OPENROUTER_ENV:-$C/secrets/openrouter.env}"
    [ -r "$KEYFILE" ] || { echo "no readable OpenRouter key file at $KEYFILE (MCU_OPENROUTER_ENV)" >&2; exit 1; }
    export CODEX_BIN="$PWD/scripts/codex-openrouter.sh" MCU_CODEX_AUTH=none
    export CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
    export CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-1050000}"
    MODEL="--model openai/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api/v1";;
  api) export CODEX_BIN="$HOME/ccr/bin/codex"; unset MCU_CODEX_AUTH;;
  nyu) export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  *) echo "ACCOUNT must be openrouter, api or nyu" >&2; exit 2;;
esac
SEED="$PWD/output/of3r_mfm/episode_001/memory"
[ -f "$SEED/logs.txt" ] || { echo "seed $SEED has no logs.txt" >&2; exit 1; }
[ -d "$SEED/previous/life_1" ] || { echo "seed $SEED carries no life_1" >&2; exit 1; }
STEPS=100000
if [ -n "${SMOKE:-}" ]; then STEPS="$SMOKE"; ARM="g4smoke_${ARM_KIND}_mfm"; GP=$SGP; PP=$SPP; WALL="${WALL:-30m}"; fi
for p in "$GP" "$PP"; do ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$p\$" && { echo "port $p is in use" >&2; exit 1; }; done
echo "arm=$ARM ($ARM_KIND) mcu=$MCU @ $(git -C . rev-parse --short HEAD) mfm=$MFM_ROOT @ $(git -C "$MFM_ROOT" rev-parse --short HEAD)"
echo "account=${ACCOUNT:-openrouter} codex=$CODEX_BIN model: $MODEL frames: $FS steps: $STEPS wall: ${WALL:-14h} ports: $GP/$PP"
TASK=ender_dragon ARM="$ARM" GP="$GP" PP="$PP" STEPS="$STEPS" SESSION_TURNS="$ST" COMPACT="$CM" WALL="${WALL:-14h}" \
  EXTRA_ONLY=1 EXTRA_SEEDS="$SEED" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
