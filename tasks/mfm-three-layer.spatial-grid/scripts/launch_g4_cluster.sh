#!/usr/bin/env bash
# The gen-4 baseline wave on the Harvard cluster (sbatch), 2026-09-10: VISTA and logbook
# on the gen-4 MIN chassis (MCU branch gen4-min-vista = gen4-cc + the vista arm), for
# ender_dragon and mine_diamond_from_scratch. The Collab-host twin is launch_g4.sh.
#
#   bash launch_g4_cluster.sh smoke                 # the three 150-step smokes (vista, logbook codex, logbook claude)
#   bash launch_g4_cluster.sh wave                  # all eight arms, staggered 3 min apart
#   bash launch_g4_cluster.sh one vista   gpt6  dragon    # one arm: <vista|logbook> <gpt56|gpt6|opus> <dragon|diamond>
#   DRY=1 bash launch_g4_cluster.sh wave            # print the sbatch lines only
#
# Settings shared with of3m_mfm (the MIN reference, 2026-09-10): effort high, frames
# 320x180, one thread per life compacted by codex (--session-turns 0 --compact; the vista
# arm ignores both -- its thread lives by its own checkpoint protocol), dragon = 100,000
# steps under a 14 h wall (here: sbatch -t 14:30, no stop_arm watchdog -- the report is
# flushed every 200 steps and on the last step), diamond = 12,000 steps (the lad ladder's
# budget). Route: the ChatGPT-subscription codex account through codex 0.153.4
# (gpt-5.6-sol, gpt-6-astra) and the user's Claude login through Claude Code 2.1.266
# (claude-opus-5, --cli claude). NOT the OpenRouter route of3m_mfm ran on -- a route
# difference to record beside every score. NO carry for any arm here: the of3r seed lives
# are not on this host, and vista has no previous-life seed anyway.
# Every arm is its own sbatch job (own ports, display, codex/claude home); jobs are
# staggered because two engines starting in the same second on one node race for :99
# and /tmp/lwjgl (mcu-coscheduled-arms-collide). Tell-tale of a victim: COMPLETED in ~90 s.
set -euo pipefail
MODE="${1:?usage: launch_g4_cluster.sh <smoke|wave|one ...>}"
U=/n/holylfs06/LABS/sham_lab/Users/chloe00
export MCU_ROOT="${MCU_ROOT:-$U/MCU-gen4-vista}"
export PYTHONPATH="${MFM_ROOT:-$U/MFM}"
export CODEX_BIN="${CODEX_BIN:-$U/codex-node-0.153/bin/codex}"
export MCU_CODEX_AUTH="${MCU_CODEX_AUTH:-$HOME/.codex/runtime-home/auth.json}"
export MCU_CLAUDE_AUTH="${MCU_CLAUDE_AUTH:-$HOME/.claude/.credentials.json}"
cd "$MCU_ROOT"
git merge-base --is-ancestor 6dd70f44 HEAD || { echo "$MCU_ROOT is not at gen4-min-vista (needs 6dd70f44)" >&2; exit 1; }
[ -d "$PYTHONPATH/mfm/vista" ] || { echo "$PYTHONPATH carries no mfm/vista" >&2; exit 1; }
[ -x "$CODEX_BIN" ] || { echo "no codex at $CODEX_BIN" >&2; exit 1; }
[ -e "$MCU_CODEX_AUTH" ] || { echo "no codex credential at $MCU_CODEX_AUTH" >&2; exit 1; }
[ -e "$MCU_CLAUDE_AUTH" ] || { echo "no claude credential at $MCU_CLAUDE_AUTH" >&2; exit 1; }
mkdir -p logs output slurm/logs
FS="${FRAME_SIZE:-320x180}"; EFF="${EFFORT:-high}"
N=0
submit() {  # submit <agent> <model-key> <task-key> [steps] [extra sbatch args...]
  local agent="$1" mk="$2" tk="$3" steps="${4:-}"; shift 3; [ $# -gt 0 ] && shift
  local mid cli=codex task arm tflag
  case "$mk" in gpt56) mid=gpt-5.6-sol;; gpt6) mid=gpt-6-astra;; opus) mid=claude-opus-5; cli=claude;; *) echo "model key $mk" >&2; return 2;; esac
  case "$tk" in dragon) task=ender_dragon; steps="${steps:-100000}"; tflag="-t ${WALL:-14:30:00}";; diamond) task=mine_diamond_from_scratch; steps="${steps:-12000}"; tflag="";; *) echo "task key $tk" >&2; return 2;; esac
  [ "$agent" = vista ] && [ "$cli" = claude ] && { echo "vista runs codex app-server only" >&2; return 2; }
  if [ "$agent" = vista ]; then arm="g4v_${tk}"; else arm="g4l_${mk}_${tk}"; fi
  [ -n "${ARM_SUFFIX:-}" ] && arm="${arm}${ARM_SUFFIX}"
  local begin="--begin=now+$((N*3))minutes"; N=$((N+1))
  local cmd=(sbatch -J "mcu-$arm" $tflag $begin "$@" slurm/arm.sbatch "$agent" "$arm" "$task" "$steps"
             --cli "$cli" --session-turns 0 --compact
             --wm-extra "--model $mid --reasoning-effort $EFF --frame-size $FS")
  echo "${cmd[*]}"
  [ "${DRY:-0}" = 1 ] || "${cmd[@]}"
}
case "$MODE" in
  smoke)  ARM_SUFFIX=_smoke submit vista gpt6 dragon 150 -t 02:00:00
          ARM_SUFFIX=_smoke submit logbook gpt6 dragon 150 -t 02:00:00
          ARM_SUFFIX=_smoke submit logbook opus dragon 150 -t 02:00:00;;
  wave)   for tk in dragon diamond; do
            submit vista gpt6 "$tk"
            for mk in gpt56 gpt6 opus; do submit logbook "$mk" "$tk"; done
          done;;
  one)    submit "${2:?agent}" "${3:?model}" "${4:?task}" "${5:-}";;
  *) echo "mode must be smoke, wave or one" >&2; exit 2;;
esac
squeue -u "$(id -un)" -o "%.10i %.24j %.9T %.8M %.14R" 2>/dev/null | tail -n +1
