#!/usr/bin/env bash
# The gen-4 baseline wave on FASRC (sbatch), 2026-09-10: VISTA and logbook on the gen-4
# MIN chassis (MCU worktree MCU-gen4-vista, branch gen4-min-vista = gen4-cc + the vista
# arm, 6dd70f44), for ender_dragon and mine_diamond_from_scratch. The sibling of
# launch_g4_fasrc.sh (the direct arms) and launch_g4.sh (the collab host).
#
#   bash launch_g4_cluster.sh smoke                    # three 150-step smokes: vista, logbook codex, logbook claude
#   bash launch_g4_cluster.sh wave                     # all eight arms, staggered 3 min apart
#   bash launch_g4_cluster.sh one vista   gpt6  dragon # one arm: <vista|logbook> <gpt56|gpt6|opus> <dragon|diamond>
#   MODELS="gpt56 gpt6" ... restricts the wave's logbook models; BEGIN0=<minutes> shifts every begin
#   time (a second invocation must not start in the same minute as the first's arms).
#   DRY=1 ... prints the sbatch lines; EXCLUDE=n1,n2 keeps the jobs off those nodes (added to the
#   nodes running this user's mcu jobs at submit time -- two engines starting together on one
#   node race for the display and /tmp/lwjgl).
#
# Same settings as of3m_mfm (the MIN reference): the OpenRouter route (openai/<model>
# via codex 0.153.4 with the key by auth.command, anthropic/claude-opus-5 via Claude Code
# 2.1.266 with the key by apiKeyHelper; no proxy on this host), effort high, frames
# 320x180, one thread per life compacted by codex (--session-turns 0 --compact; the vista
# arm ignores both -- its thread lives by its own checkpoint protocol), dragon 100,000
# steps under a 14 h wall (arm_wall.sbatch: stop_arm.py at WALL, the report and log up
# to then stand), diamond 12,000 steps under 24 h. Chassis flags only for these arms
# (--frame-size): the purple agent refuses the mfm flags outside --memory mfm.
# NO carry for any arm here: the of3r seed lives are not on this host, and vista has no
# previous-life seed anyway. Record beside every score.
set -euo pipefail
MODE="${1:?usage: launch_g4_cluster.sh <smoke|wave|one <vista|logbook> <gpt56|gpt6|opus> <dragon|diamond> [steps]>}"
U=/n/holylfs06/LABS/sham_lab/Users/chloe00
export MCU_ROOT="${MCU_ROOT:-$U/MCU-gen4-vista}" MFM_ROOT="${MFM_ROOT:-$U/MFM}"
WALLSB="$(cd "$(dirname "$0")" && pwd)/arm_wall.sbatch"
KEYFILE="${MCU_OPENROUTER_ENV:-$HOME/.codex-eval/openrouter.env}"
[ -r "$KEYFILE" ] || { echo "no readable OpenRouter key file at $KEYFILE" >&2; exit 1; }
[ -f "$WALLSB" ] || { echo "no $WALLSB (the wall-capped sbatch wrapper)" >&2; exit 1; }
git -C "$MCU_ROOT" merge-base --is-ancestor 6dd70f44 HEAD || { echo "$MCU_ROOT is not at gen4-min-vista (needs 6dd70f44)" >&2; exit 1; }
[ -z "$(git -C "$MCU_ROOT" status --porcelain -- mcu_worldmodel scripts slurm)" ] || { echo "$MCU_ROOT has uncommitted changes under mcu_worldmodel/, scripts/ or slurm/" >&2; exit 1; }
[ -d "$MFM_ROOT/mfm/vista" ] || { echo "$MFM_ROOT carries no mfm/vista" >&2; exit 1; }
git -C "$MFM_ROOT" merge-base --is-ancestor e87552c HEAD || { echo "$MFM_ROOT is behind MFM e87552c (the vista provider config)" >&2; exit 1; }
CODEX_REAL="$U/codex-node-0.153/bin/codex"; CLAUDE_REAL="$HOME/.nvm/versions/node/v24.19.0/bin/claude"
[ -x "$CODEX_REAL" ] && [ -x "$CLAUDE_REAL" ] || { echo "CLI binary missing ($CODEX_REAL / $CLAUDE_REAL)" >&2; exit 1; }
mkdir -p "$MCU_ROOT/logs" "$MCU_ROOT/output" "$MCU_ROOT/slurm/logs"
export MCU_OPENROUTER_PROXY=""
FS="${FRAME_SIZE:-320x180}"; EFF="${EFFORT:-high}"
BUSY="$(squeue -u "$(id -un)" -h -t R -o %R 2>/dev/null | grep -v '(' | sort -u | paste -sd, -)"
EXCL="${EXCLUDE:+$EXCLUDE,}${BUSY}"; EXCL="${EXCL%,}"
N="${BEGIN0:-0}"
submit() {  # submit <vista|logbook> <gpt56|gpt6|opus> <dragon|diamond> [steps]
  local agent="$1" mk="$2" tk="$3" steps="${4:-}"
  local cli=codex mid model task wall tlim arm VISTA_OPUS=0
  case "$mk" in
    gpt56) mid=gpt-5.6-sol;  CW=400000;;
    gpt6)  mid=gpt-6-astra;  CW=1050000;;
    opus)  mid=claude-opus-5; cli=claude;;
    *) echo "model key $mk (gpt56|gpt6|opus)" >&2; return 2;;
  esac
  case "$tk" in
    dragon)  task=ender_dragon;             steps="${steps:-100000}"; wall="${WALL:-14h}"; tlim=15:30:00;;
    diamond) task=mine_diamond_from_scratch; steps="${steps:-12000}";  wall="${WALL:-24h}"; tlim=25:30:00;;
    *) echo "task key $tk (dragon|diamond)" >&2; return 2;;
  esac
  if [ "$agent" = vista ] && [ "$cli" = claude ]; then
    # VISTA is a codex app-server thread; there is no Claude Code twin of its protocol. With
    # ALLOW_VISTA_OPUS_CODEX=1 the thread asks OpenRouter for anthropic/claude-opus-5 through the
    # same codex channel -- a feasibility probe, NOT the "Opus through Claude Code" rule the mfm
    # and logbook opus arms follow (user decision 2026-09-10).
    [ "${ALLOW_VISTA_OPUS_CODEX:-0}" = 1 ] || { echo "vista runs codex app-server only (ALLOW_VISTA_OPUS_CODEX=1 to probe opus through it)" >&2; return 2; }
    cli=codex; VISTA_OPUS=1; CW=200000
  fi
  # vista arm names carry the model since the gpt-5.6/opus arms (22:55); the first two gpt-6 arms
  # launched 21:45 kept the short names g4v_dragon / g4v_diamond.
  if [ "$agent" = vista ]; then arm="g4v_${mk}_${tk}"; else arm="g4l_${mk}_${tk}"; fi
  if [ -n "${SMOKE:-}" ]; then steps="$SMOKE"; arm="${arm}_smoke"; wall=40m; tlim=01:30:00; fi
  # The route, per CLI -- the same exports as launch_g4_fasrc.sh, so the arms share a channel.
  local -a envs=()
  if [ "$cli" = codex ]; then
    envs=(CODEX_BIN="$MCU_ROOT/scripts/codex-openrouter.sh" MCU_CODEX_REAL="$CODEX_REAL" MCU_CODEX_AUTH=none
          CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
          CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-$CW}")
    local vendor=openai; [ "${VISTA_OPUS:-0}" = 1 ] && vendor=anthropic
    model="--model $vendor/$mid --reasoning-effort $EFF --base-url https://openrouter.ai/api/v1"
  else
    envs=(MCU_CLAUDE_ROOT="${MCU_CLAUDE_ROOT:-$U/claude-homes}" MCU_CLAUDE_ACCOUNT=openrouter MCU_OPENROUTER_ENV="$KEYFILE"
          MCU_CLAUDE_BIN="$MCU_ROOT/scripts/claude-openrouter.sh" MCU_CLAUDE_REAL="$CLAUDE_REAL" MCU_CLAUDE_SANDBOX_TOOLS=/usr/bin)
    model="--model anthropic/$mid --reasoning-effort $EFF --base-url https://openrouter.ai/api"
  fi
  local begin="--begin=now+${N}minutes"; N=$((N+3))
  local -a sb=(sbatch -J "$arm" -t "$tlim" -o "$MCU_ROOT/slurm/logs/%x-%j.out" -e "$MCU_ROOT/slurm/logs/%x-%j.err" "$begin"
               ${EXCL:+--exclude="$EXCL"}
               "$WALLSB" "$agent" "$arm" "$task" "$steps" "$wall"
               --cli "$cli" --session-turns 0 --compact --wm-extra "$model --frame-size $FS")
  echo "arm=$arm agent=$agent cli=$cli model=$mid task=$task steps=$steps wall=$wall tlim=$tlim exclude=${EXCL:-none}"
  echo "  ${sb[*]}"
  [ "${DRY:-0}" = 1 ] && return 0
  # The submitting shell is often a Claude Code session; its identity must not ride into the job.
  env -u CLAUDECODE -u CLAUDE_CONFIG_DIR -u CLAUDE_CODE_SESSION_ID "${envs[@]}" "${sb[@]}"
}
case "$MODE" in
  smoke)  SMOKE="${SMOKE:-150}"; submit vista gpt6 dragon; submit logbook gpt6 dragon; submit logbook opus dragon;;
  wave)   for tk in dragon diamond; do submit vista gpt6 "$tk"; for mk in ${MODELS:-gpt56 gpt6 opus}; do submit logbook "$mk" "$tk"; done; done;;
  one)    submit "${2:?agent}" "${3:?model}" "${4:?task}" "${5:-}";;
  *) echo "mode must be smoke, wave or one" >&2; exit 2;;
esac
[ "${DRY:-0}" = 1 ] || squeue -u "$(id -un)" -o "%.10i %.26j %.9T %.8M %.14R"
