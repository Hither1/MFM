#!/usr/bin/env bash
# The collab-host twin of launch_g4_fasrc.sh's ABL= knob (ABLATIONS_RUNBOOK.md, 2026-09-20):
# ONE ablation of the MFM arm on mine_diamond_from_scratch, 12,000 steps, no carry, through
# the API-key codex account (~/ccr/bin/codex, ACCOUNT=api in launch_g4.sh) on gpt-5.6-sol high.
#   bash launch_ablations_collab.sh noimg    # g4_mfm_sol_diamond_noimg  9870/10870  --no-history-images
#   bash launch_ablations_collab.sh flat     # g4_mfm_sol_diamond_flat   9871/10871  --flat-retrieval (no --retrieval)
#   bash launch_ablations_collab.sh nocons   # g4_mfm_sol_diamond_nocons 9872/10872  --no-consolidation
#   SMOKE=150 bash launch_ablations_collab.sh <abl>   # g4smoke_sol_diamond_<abl>, ports +10, WALL 40m
#   SUFFIX=v2 appends _v2 to the arm name (a second life; the bare name would erase the first).
#   MID=... overrides the model id; WALL (default 24h) the wall-clock cap.
# Code: MCU-ablate (branch gen4-min-vista, b931052) + MFM (kicad-results-0913, c644349) as MFM_ROOT.
# Each arm gets its own Xvfb display number (MCU_DISPLAY_NUM) so three arms can share this host
# without racing `xvfb-run -a`; launch-og.sh detaches the arm and writes logs/<arm>_launch.{log,pid}.
set -euo pipefail
ABL="${1:?usage: launch_ablations_collab.sh <noimg|flat|nocons>}"
C=/datapool/data3/storage/ruihan/data_share/jh/Collab
MCU="$C/MCU-ablate"; export MFM_ROOT="$C/MFM"
cd "$MCU"
git -C . merge-base --is-ancestor b931052d HEAD || { echo "$MCU is not at gen4-min-vista b931052" >&2; exit 1; }
git -C "$MFM_ROOT" merge-base --is-ancestor c644349 HEAD || { echo "$MFM_ROOT is behind MFM c644349 (the ablation store)" >&2; exit 1; }
[ -z "$(git -C . status --porcelain -- mcu_worldmodel scripts)" ] || { echo "$MCU has uncommitted changes under mcu_worldmodel/ or scripts/" >&2; exit 1; }
[ -z "$(git -C "$MFM_ROOT" status --porcelain -- mfm)" ] || { echo "$MFM_ROOT has uncommitted changes under mfm/" >&2; exit 1; }
export MCU_CODEX_ROOT="$C/codex-homes"
export no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}" NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"
# The API-key account: ~/ccr/bin/codex with codex-home.sh's default credential (~/ccr/.codex/auth.json).
export CODEX_BIN="$HOME/ccr/bin/codex"; unset MCU_CODEX_AUTH
MID="${MID:-gpt-5.6-sol}"; EFF=high; FS="${FRAME_SIZE:-320x180}"
MODEL="--model $MID --reasoning-effort $EFF"
# The reference arm's flag set, verbatim (ABLATIONS_RUNBOOK.md section 3).
BASE="--expect --frames --retrieval --no-event-sheet --frame-size $FS --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
case "$ABL" in
  noimg)  EXTRA="--no-history-images"; GP=9870; PP=10870; DISP=70;;
  # --retrieval is computed from the index this arm takes away; the agent refuses the pair.
  flat)   EXTRA="--flat-retrieval"; BASE="${BASE/--retrieval /}"; GP=9871; PP=10871; DISP=71;;
  nocons) EXTRA="--no-consolidation"; GP=9872; PP=10872; DISP=72;;
  *) echo "abl must be noimg, flat or nocons" >&2; exit 2;;
esac
tag_of() { case "$1" in gpt-5.6-sol) echo sol;; gpt-6-astra) echo gpt6;; *) echo "$1" | tr -c 'a-z0-9\n' _;; esac; }
ARM="g4_mfm_$(tag_of "$MID")_diamond_${ABL}${SUFFIX:+_$SUFFIX}"
STEPS=12000; WALL="${WALL:-24h}"
if [ -n "${SMOKE:-}" ]; then STEPS="$SMOKE"; ARM="g4smoke_$(tag_of "$MID")_diamond_${ABL}${SUFFIX:+_$SUFFIX}"; GP=$((GP+10)); PP=$((PP+10)); DISP=$((DISP+10)); WALL="${WALL_SMOKE:-40m}"; fi
for p in "$GP" "$PP"; do ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$p\$" && { echo "port $p is in use" >&2; exit 1; }; done
[ -e "/tmp/.X${DISP}-lock" ] && { echo "display :$DISP is taken (/tmp/.X${DISP}-lock)" >&2; exit 1; }
export MCU_DISPLAY_NUM="$DISP"
echo "arm=$ARM abl=$ABL mcu=$MCU @ $(git -C . rev-parse --short HEAD) mfm=$MFM_ROOT @ $(git -C "$MFM_ROOT" rev-parse --short HEAD)"
echo "account=api bin=$CODEX_BIN ($("$CODEX_BIN" --version 2>/dev/null | head -1)) model: $MODEL frames: $FS steps: $STEPS wall: $WALL ports: $GP/$PP display: :$DISP"
TASK=mine_diamond_from_scratch ARM="$ARM" GP="$GP" PP="$PP" STEPS="$STEPS" SESSION_TURNS=0 COMPACT=1 WALL="$WALL" \
  AGENT=mfm CLI=codex NO_SEEDS=1 WM_EXTRA="$MODEL $BASE $EXTRA" bash scripts/launch-og.sh
