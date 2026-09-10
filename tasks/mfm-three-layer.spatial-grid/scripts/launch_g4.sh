#!/usr/bin/env bash
# Generation 4 (2026-09-10): the head-to-head of two settings, both seeded with of3r (16/24,
# gen 2; its previous/ already carries of3, so the workshop sees both lives). Plan and
# rationale: tasks/mfm-three-layer.spatial-grid/analysis/gen4_plan_2026-09-10.md (sections 8, 11).
#   bash launch_g4.sh min    # of3m_mfm 9133/9143: gen 2 exactly + the three edits (MFM-grid-min-mcu,
#                            #   branch gen4-min), frames 320x180 as of3r had them
#   bash launch_g4.sh full   # of3f_mfm 9132/9142: gen 2 + gen 3's neutral fixes + the three edits, none
#                            #   of gen 3's doctrine (MFM-grid-merge-mcu, branch gen4-full), frames 640x360
#   bash launch_g4.sh cc     # of3c_mfm 9134/9144: the MIN arm through Claude Code driving Opus 5 via
#                            #   OpenRouter (MFM-grid-cc-mcu, branch gen4-cc = gen4-min + the claude channel);
#                            #   same contract, seeds, frames; CLI=claude, key via apiKeyHelper, sandbox on
#   bash launch_g4.sh lb     # of3l_lb 9135/9145: the text-only PRO-LONG baseline -- --agent logbook on the
#                            #   same chassis and model as MIN, memory = one append-only logs.txt, the two
#                            #   earlier lives carried as ONE text file (--seed-log), no frames tool, no
#                            #   skills/own/reflexes/retrieval
#   SMOKE=150 bash launch_g4.sh min|full|cc|lb   # g4smoke_<arm>_*, 150 steps, ports 9127/9137 (min),
#                            #   9126/9136 (full), 9128/9138 (cc), 9129/9139 (lb), WALL 30m
#   MID=claude-haiku-4.5 SMOKE=150 bash launch_g4.sh cc   # a cheap plumbing smoke of the claude channel
# Both arms: gpt-6-astra high through OpenRouter (ACCOUNT=openrouter default; api|nyu as in
# launch_g3.sh), one codex thread for the life compacted by codex (SESSION_TURNS=0, COMPACT=1),
# STEPS=100000, WALL 14h (WALL env overrides), TASK=ender_dragon, carry-only seeding
# (EXTRA_ONLY=1, no --sites). FRAME_SIZE overrides the arm's default.
# The three model-facing edits shared by both arms (analysis/gen4_contract_diff_{min,full}.txt):
# the starving example eats what you carry when the bar drops below 18, the hunger line in
# Safety, then-now on arrival at a remembered place + the episode id beside each digest place.
set -euo pipefail
ARM_KIND="${1:?usage: launch_g4.sh <min|full|cc|lb>}"
C=/datapool/data3/storage/ruihan/data_share/jh/Collab
CLI=codex; AGENT=mfm
case "$ARM_KIND" in
  min)  MCU="$C/MFM-grid-min-mcu";   export MFM_ROOT="$C/MFM-grid-min"; ARM=of3m_mfm; GP=9133; PP=9143; FS="${FRAME_SIZE:-320x180}"; NEED=bfd31b31; SGP=9127; SPP=9137;;
  full) MCU="$C/MFM-grid-merge-mcu"; export MFM_ROOT="$C/MFM-grid";     ARM=of3f_mfm; GP=9132; PP=9142; FS="${FRAME_SIZE:-640x360}"; NEED=a7dbe7ba; SGP=9126; SPP=9136;;
  cc)   MCU="$C/MFM-grid-cc-mcu";    export MFM_ROOT="$C/MFM-grid-min"; ARM=of3c_mfm; GP=9134; PP=9144; FS="${FRAME_SIZE:-320x180}"; NEED=902f1313; SGP=9128; SPP=9138; CLI=claude;;
  lb)   MCU="$C/MFM-grid-cc-mcu";    export MFM_ROOT="$C/MFM-grid-min"; ARM=of3l_lb;  GP=9135; PP=9145; FS="${FRAME_SIZE:-320x180}"; NEED=902f1313; SGP=9129; SPP=9139; AGENT=logbook;;
  *) echo "arm must be min, full, cc or lb" >&2; exit 2;;
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
# The logbook baseline keeps the chassis (executor, perception, caps, frame size) and sheds
# every memory mechanism: no frames tool, no retrieval, no expect protocol, no minimal/mfm
# contract, no skills, no own files or reflexes (the purple agent refuses those flags
# outside --memory mfm; the harness's own lava/fall stops stay, as in every logbook run so
# far). Its contract is the logbook one ("your memory is one append-only log").
[ "$AGENT" = logbook ] && BASE="--frame-size $FS"
EFF=high
if [ "$CLI" = claude ]; then MID="${MID:-claude-opus-5}"; else MID="${MID:-gpt-6-astra}"; fi
MODEL="--model $MID --reasoning-effort $EFF"
KEYFILE="${MCU_OPENROUTER_ENV:-$C/secrets/openrouter.env}"
case "${ACCOUNT:-openrouter}" in
  openrouter)
    [ -r "$KEYFILE" ] || { echo "no readable OpenRouter key file at $KEYFILE (MCU_OPENROUTER_ENV)" >&2; exit 1; }
    if [ "$CLI" = claude ]; then
      # Claude Code against OpenRouter's Anthropic-compatible endpoint. The key reaches the
      # CLI through settings apiKeyHelper (claude-home.sh writes the helper into the arm's
      # config dir); the sandbox denies the model's shell and Read tool both that dir and
      # the secrets dir; claude-openrouter.sh adds the proxy and the bwrap/socat PATH.
      export MCU_CLAUDE_ROOT="$C/claude-homes" MCU_CLAUDE_ACCOUNT=openrouter MCU_OPENROUTER_ENV="$KEYFILE"
      export MCU_CLAUDE_BIN="$PWD/scripts/claude-openrouter.sh"
      MODEL="--model anthropic/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api"
    else
      export CODEX_BIN="$PWD/scripts/codex-openrouter.sh" MCU_CODEX_AUTH=none
      export CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
      export CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-1050000}"
      MODEL="--model openai/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api/v1"
    fi;;
  subscription)
    # A Claude subscription (Max) account: the per-arm config dir symlinks one live
    # .credentials.json (MCU_CLAUDE_AUTH, default ~/.claude-eval/.credentials.json) or takes
    # a `claude setup-token` token from MCU_CLAUDE_OAUTH_TOKEN; the config dir is deny-read.
    [ "$CLI" = claude ] || { echo "ACCOUNT=subscription is for the claude arms" >&2; exit 2; }
    export MCU_CLAUDE_ROOT="$C/claude-homes"; unset MCU_CLAUDE_ACCOUNT
    export MCU_CLAUDE_BIN="$PWD/scripts/claude-openrouter.sh" MCU_OPENROUTER_PROXY=""
    MODEL="--model $MID --reasoning-effort $EFF";;
  api) export CODEX_BIN="$HOME/ccr/bin/codex"; unset MCU_CODEX_AUTH;;
  nyu) export CODEX_BIN="$HOME/.nvm/versions/node/v22.18.0/bin/codex" MCU_CODEX_AUTH="$HOME/.codex/runtime-home/auth.json";;
  *) echo "ACCOUNT must be openrouter, subscription, api or nyu" >&2; exit 2;;
esac
SEED="$C/MFM-grid/MCU/output/of3r_mfm/episode_001/memory"
[ -f "$SEED/logs.txt" ] || { echo "seed $SEED has no logs.txt" >&2; exit 1; }
[ -d "$SEED/previous/life_1" ] || { echo "seed $SEED carries no life_1" >&2; exit 1; }
SEED_LOG=""
if [ "$AGENT" = logbook ]; then
  # The two earlier lives as one text file, oldest first -- the whole carry-over of the
  # text-only arm. Built once, deterministic (byte concatenation of the two logs.txt).
  SEED_LOG="$PWD/output/seed_logs/of3r_two_lives_logs.txt"
  if [ ! -f "$SEED_LOG" ]; then
    mkdir -p "$(dirname "$SEED_LOG")"
    { echo "==== LIFE 1 (an earlier life in this world; 10/24) ===="; cat "$SEED/previous/life_1/logs.txt";
      echo; echo "==== LIFE 2 (the life after it; 16/24) ===="; cat "$SEED/logs.txt"; } > "$SEED_LOG"
  fi
  echo "seed log: $SEED_LOG ($(wc -l < "$SEED_LOG") lines)"
fi
STEPS=100000
if [ -n "${SMOKE:-}" ]; then STEPS="$SMOKE"; ARM="g4smoke_${ARM_KIND}_${AGENT}"; GP=$SGP; PP=$SPP; WALL="${WALL:-30m}"; fi
for p in "$GP" "$PP"; do ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$p\$" && { echo "port $p is in use" >&2; exit 1; }; done
echo "arm=$ARM ($ARM_KIND) mcu=$MCU @ $(git -C . rev-parse --short HEAD) mfm=$MFM_ROOT @ $(git -C "$MFM_ROOT" rev-parse --short HEAD)"
echo "account=${ACCOUNT:-openrouter} cli=$CLI agent=$AGENT bin=${CODEX_BIN:-}${MCU_CLAUDE_BIN:-} model: $MODEL frames: $FS steps: $STEPS wall: ${WALL:-14h} ports: $GP/$PP"
if [ "$AGENT" = logbook ]; then
  TASK=ender_dragon ARM="$ARM" GP="$GP" PP="$PP" STEPS="$STEPS" SESSION_TURNS="$ST" COMPACT="$CM" WALL="${WALL:-14h}" \
    AGENT=logbook CLI="$CLI" NO_SEEDS=1 SEED_LOG="$SEED_LOG" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
else
  TASK=ender_dragon ARM="$ARM" GP="$GP" PP="$PP" STEPS="$STEPS" SESSION_TURNS="$ST" COMPACT="$CM" WALL="${WALL:-14h}" \
    AGENT=mfm CLI="$CLI" EXTRA_ONLY=1 EXTRA_SEEDS="$SEED" WM_EXTRA="$MODEL $BASE" bash scripts/launch-og.sh
fi
