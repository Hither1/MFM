#!/usr/bin/env bash
# One experiment arm of the MCU A2A benchmark: green server, purple agent, eval client.
#
#   sbatch slurm/arm.sbatch prolong    pl_dragon1 ender_dragon
#   sbatch slurm/arm.sbatch worldmodel wm_dragon1 ender_dragon
#
# This is the batch wrapper for scripts/run-arm.sh, which is written for an interactive
# host. What it adds is everything that shell script assumes someone did by hand:
#
#  * No GPU. Both agents are API-driven coding agents, not neural policies -- MinecraftSim
#    runs on CPU. (--agent steve1 would need one; it is not launchable from here.)
#  * The cluster's environment instead of env.sh. env.sh describes a rootless host with a
#    user-local JDK under $MCU_PREFIX, which does not exist here; system java is 1.8 and
#    the engine is symlinked node-local by mcu_worldmodel/setup_env.sh. Hence
#    MCU_SKIP_ENV_SH=1 plus the exports below.
#  * A display number derived from the job id, not `xvfb-run -a`, which races two jobs
#    onto one X server -- see the note in worldmodel.sbatch.
#  * Ports derived from the job id, so two arms submitted together cannot collide even if
#    the scheduler puts them on one node.
#
# The arms are independent by construction: own ports, own output dir, own codex home.
# Submit one job per arm rather than backgrounding two in a single job.
#SBATCH -J mcu-arm
#SBATCH -p sapphire
#SBATCH -c 12
#SBATCH --mem=48G
# 2.5 days, not 24 h. A PRO-LONG-cadence arm (prolong, plmfm: one model call per
# 1-2 ticks) needs 18-29 h for 12,000 steps at dm4's pace; at 24 h SLURM killed the
# tree mid-episode and result.json was never written. sapphire allows 3 days.
#SBATCH -t 2-12:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

set -euo pipefail
AGENT=${1:?usage: sbatch arm.sbatch <worldmodel|wmlite|logbook|mfm|vista|direct|prolong|plmfm> <arm-name> [task] [steps]}
ARM=${2:?usage: sbatch arm.sbatch <worldmodel|wmlite|logbook|mfm|vista|direct|prolong|plmfm> <arm-name> [task] [steps]}
TASK=${3:-ender_dragon}
STEPS=${4:-12000}

# Overridable so a second checkout (a git worktree with `.venv` symlinked to this
# one) can run a wave while jobs still execute the scripts of this checkout --
# bash reads a running script by byte offset, so those must not be edited.
ROOT=${MCU_ROOT:-/n/holylfs06/LABS/sham_lab/Users/chloe00/MCU}
cd "$ROOT"
mkdir -p slurm/logs

echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="
echo "agent=$AGENT arm=$ARM task=$TASK steps=$STEPS"

# The engine, node-local, with only the 466 MB jar symlinked back to netscratch. Java
# stat-s its working directory at FileSystem init and netscratch returns intermittent
# ESTALE, which kills the JVM before Minecraft starts. See setup_env.sh.
export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export JAVA_HOME=${JAVA_HOME:-/usr}
export MCU_SKIP_ENV_SH=1

# The ChatGPT-subscription credential, read through a symlink so a refresh lands on one
# file. codex-home.sh symlinks this into the arm's own home; it is never copied, because
# each copy carries the same single-use refresh token and the second arm to refresh gets
# "your refresh token was already used" and 401s for the rest of the run.
export MCU_CODEX_AUTH="${MCU_CODEX_AUTH:-$HOME/.codex/runtime-home/auth.json}"
# /var/tmp, not /tmp: codex refuses to create its PATH-alias helpers under a temp dir
# that is wiped at boot. Node-local either way, which is what sqlite needs.
export MCU_CODEX_ROOT="${MCU_CODEX_ROOT:-/var/tmp/mcu-codex-$(id -un)}"

# Unset, or codex takes the API key over the subscription login above.
unset OPENAI_API_KEY

export MCU_DISPLAY_NUM=$(( (SLURM_JOB_ID % 55000) + 200 ))
GREEN_PORT=$(( 9000 + (SLURM_JOB_ID % 900) ))
PURPLE_PORT=$(( GREEN_PORT + 1000 ))
echo "display=:$MCU_DISPLAY_NUM green=$GREEN_PORT purple=$PURPLE_PORT"

# The codex rollouts are node-local (/var/tmp) and are the only record of what codex
# ran inside a turn's code-mode cells: the report's `tool_errors` is counted from them
# and the `--json` event stream omits the cells. Copied beside the run on exit, success
# or not, because once the node is full again they cannot be read (lad3, 2026-09-05:
# 23 tool errors and a copy job queued for a day).
copy_rollouts() {
    local sess="$MCU_CODEX_ROOT/$ARM/sessions" dst="$ROOT/output/$ARM/codex_sessions"
    if [ -d "$sess" ]; then
        mkdir -p "$dst" && cp -r "$sess/." "$dst/" \
            && echo "rollouts copied to $dst: $(find "$dst" -name 'rollout-*.jsonl' | wc -l)"
    fi
}
trap copy_rollouts EXIT

scripts/run-arm.sh --arm "$ARM" --agent "$AGENT" --task "$TASK" \
    --green-port "$GREEN_PORT" --purple-port "$PURPLE_PORT" \
    --steps "$STEPS" "${@:5}"

echo "finished=$(date -Is)"
