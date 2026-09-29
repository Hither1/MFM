#!/usr/bin/env bash
# One long-horizon episode of the world-model agent on MCU.
#
#   sbatch slurm/worldmodel.sbatch diamond outputs/d1
#   sbatch slurm/worldmodel.sbatch dragon  outputs/g1
#
# Notes on the settings that are not obvious:
#
#  * No GPU is requested. The agent is an API-driven coding agent, not a neural policy --
#    unlike the VPT/STEVE-1 baselines in RDI-Foundation/Minecraft-agentbeats, nothing here
#    runs on a GPU. What the job needs is a CPU, memory for the JVM, and a display.
#  * xvfb, because Minecraft renders through OpenGL and there is no attached display. The
#    screen has to be at least as large as MinecraftSim's render_size (640x360).
#  * MINESTUDIO_DIR must point at the extracted engine *before* python starts: MinecraftSim
#    calls check_engine() at class-definition time and prompts on stdin if the jar is
#    missing, which in a batch job is an EOFError during import.
#  * The time limit is generous because these episodes are 6,000-12,000 environment steps
#    with a model turn every few hundred; the environment is not the slow part, the turns
#    are.
#SBATCH -J mcu-worldmodel
#SBATCH -p sapphire
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 24:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

set -euo pipefail
TASK=${1:?usage: sbatch worldmodel.sbatch <diamond|dragon> [output-dir]}
OUT=${2:-outputs/${TASK}_$SLURM_JOB_ID}

ROOT=/n/holylfs06/LABS/sham_lab/Users/chloe00/MCU
cd "$ROOT"
mkdir -p slurm/logs "$OUT"

# Node-local instance dirs with the engine symlinked in; see setup_env.sh for why NFS
# breaks the JVM before Minecraft starts.
export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
# The engine bundles its own Java 8 expectations; the system java is 1.8, which is right.
export JAVA_HOME=${JAVA_HOME:-/usr}
# Codex needs a per-episode home or it inherits the account's global AGENTS.md and skills,
# which would sit ahead of this system's prompt in every turn.
export CODEX_HOME="$ROOT/$OUT/.codexhome"
mkdir -p "$CODEX_HOME"
# The point of a per-episode home is to keep the account's global AGENTS.md and personal
# skills from being prepended to every turn -- MineExplorer measured ~5-6k tokens of them
# ahead of its own system prompt. But an empty home has no credential either, so it is
# seeded with one.
#
# The API key, not a copy of ~/.codex/auth.json: that file holds a ChatGPT subscription
# token whose refresh token is already spent ("your refresh token was already used"), so
# every turn would 401. `codex login --with-api-key` writes a fresh apikey auth.json into
# $CODEX_HOME and is what this run was verified against.
#
# Two channels, and exactly one credential path is exercised. BASE_URL (or the discovery
# file slurm/vllm_server.sbatch writes when its server is ready) selects the local vLLM
# server; otherwise the hosted API. The local branch needs no login: codex authenticates
# a custom provider from env_key, which codex_backend.py sets to LOCAL_API_KEY, and vLLM
# does not check the value -- but codex refuses to start a provider whose key is unset,
# so it still has to exist.
BASE_URL="${BASE_URL:-}"
DISCOVERY="$ROOT/artifacts/servers/${SERVER_SLUG:-qwen38-27b}.json"
JQ() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$DISCOVERY" "$1"; }
if [[ -z "$BASE_URL" && -f "$DISCOVERY" ]]; then
  BASE_URL=$(JQ url)
  MODEL="${MODEL:-$(JQ model)}"
  echo "discovered local server: $BASE_URL (model=$MODEL, job=$(JQ job))"
fi
if [[ -n "$BASE_URL" ]]; then
  export LOCAL_API_KEY="${LOCAL_API_KEY:-EMPTY}"
  CHANNEL_ARGS=(--base-url "$BASE_URL")
  # Reachability is asserted here, not discovered on the first turn. A run that starts
  # against a dead advert burns its wall clock producing no-op turns, which is how the
  # credit-exhausted run failed: 22 turns, 8 environment steps, and nothing in the log
  # that named the cause.
  curl -fsS --max-time 20 "$BASE_URL/models" >/dev/null \
    || { echo "local server at $BASE_URL is not answering" >&2; exit 1; }
else
  : "${OPENAI_API_KEY:?set OPENAI_API_KEY, or sbatch slurm/vllm_server.sbatch for the local channel}"
  printenv OPENAI_API_KEY | codex login --with-api-key >/dev/null
  CHANNEL_ARGS=()
fi

# Per-turn ceiling, raised from codex_backend.py's 1800s default for the local channel.
#
# The local path decodes at ~5 tok/s (plain transformers generate, sdpa, no CUDA graphs),
# so an 8192-token turn needs ~28 minutes and 1800s cuts it off mid-generation -- which
# looks exactly like a hung model and is really a client giving up. Measured: v2 turn 1
# "timed out after 1800s; 3 events kept".
#
# 3600s covers a full-cap turn with margin. The hosted channel does not need it (it
# decodes an order of magnitude faster) so this is only raised when BASE_URL is in play.
if [[ -n "${BASE_URL:-}" ]]; then
  export CODEX_TIMEOUT="${CODEX_TIMEOUT:-3600}"
  echo "local channel: CODEX_TIMEOUT=$CODEX_TIMEOUT"
fi

PY=$HOME/miniforge3/envs/minestudio/bin/python

echo "task=$TASK out=$OUT node=$(hostname) started=$(date -Is)"
# A display number derived from the job id, NOT `xvfb-run -a`.
#
# `-a` scans for a free display and races: two jobs starting together on the same node can
# select the same number and end up sharing one X server. Measured -- diamond_v3 and
# dragon_v3 both landed on holy8a24110, and cancelling dragon at 18:55:28 killed the X
# server diamond was using, so its Minecraft lost its socket at 18:56:14 and the run died
# with "Connection refused" at ~step 200. That looked like an agent crash and was not.
#
# The job id is unique per node-at-a-time, so this cannot collide with a concurrent job.
DISPLAY_NUM=$(( (SLURM_JOB_ID % 55000) + 200 ))
echo "using display :$DISPLAY_NUM"

srun xvfb-run --server-num="$DISPLAY_NUM" -s "-screen 0 1024x768x24" \
  "$PY" -m mcu_worldmodel.run \
    --task "$TASK" \
    --output "$OUT" \
    --model "${MODEL:-gpt-5.6-sol}" \
    --effort "${EFFORT:-medium}" \
    "${CHANNEL_ARGS[@]}" \
    --codex-home "$CODEX_HOME" \
    --induction-every "${INDUCTION_EVERY:-600}" \
    --step-cap "${STEP_CAP:-400}"
echo "finished=$(date -Is)"
