#!/usr/bin/env bash
# One self-contained long-horizon episode: model server AND agent in a single job.
#
#   sbatch slurm/solo.sbatch diamond outputs/d1
#   sbatch slurm/solo.sbatch dragon  outputs/g1
#
# This replaces the tf_server.sbatch + worldmodel.sbatch pair. Why combine them:
#
#  * The GPU is idle for almost the whole episode. Measured on the 41465614/41471271
#    pair: 31 requests in 5.5 hours, `nvidia-smi` at 0% between turns. That is inherent
#    -- the agent spends its time stepping Minecraft, not decoding -- so it is not a
#    reason to split the jobs, but it does mean nothing is lost by sharing one node.
#  * The split *does* waste the tail. The server held a 48h limit against the agent's
#    24h, so after the agent hit its wall the H200 sat allocated and idle for another
#    ~23h unless someone remembered to scancel it. Here the server cannot outlive the
#    episode: it is a child of this job and dies with it.
#  * It removes the discovery race. The pair coordinated through a file in
#    artifacts/servers/, so the agent could start against a stale advert from a server
#    that had already exited -- which is how the credit-exhausted run burned its wall
#    clock on no-op turns. Here the server's readiness is a precondition of the agent
#    starting, checked in-process.
#
# The cost: this queues on gpu_h200 for the full episode length rather than putting the
# CPU-only agent on sapphire, and a startup crash in the agent burns a GPU allocation.
# If gpu_h200 is congested, the two-job form is still the better bet.
#
# Host requirements, verified present on holygpu8a12201: xvfb-run, Xvfb, java 1.8.0_504,
# the minestudio conda env, /n/netscratch and /n/holylfs06.
#SBATCH -J mcu-solo
#SBATCH -p gpu_h200
#SBATCH --gres=gpu:nvidia_h200:1
# 24 = 16 for the server + 8 for the agent, the two halves' original asks. The nodes are
# 112-core so this is not a scheduling constraint.
#SBATCH -c 24
# 224G = 192G server + 32G agent. Nodes carry ~1007G.
#SBATCH --mem=224G
#SBATCH -t 24:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

# -e is deliberately absent, matching serve_transformers.sh: this script runs background
# jobs under a trap, and `set -e` turns an expected non-zero from a poll into a silent
# exit with no diagnostic.
set -uo pipefail
TASK=${1:?usage: sbatch solo.sbatch <diamond|dragon> [output-dir]}
OUT=${2:-outputs/${TASK}_$SLURM_JOB_ID}

ROOT=/n/holylfs06/LABS/sham_lab/Users/chloe00/MCU
cd "$ROOT" || exit 1
mkdir -p slurm/logs "$OUT"

echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="
echo "task=$TASK out=$OUT"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

# ---------------------------------------------------------------- server half

# A job-scoped slug, NOT the shared "qwen38-27b".
#
# serve_transformers.sh writes artifacts/servers/$SERVER_SLUG.json and removes it on
# exit. With the default slug a solo job would clobber the advert a standalone
# tf_server.sbatch is publishing, and its cleanup would delete that server's file --
# silently stranding any worldmodel.sbatch that was using it. Scoping the slug to this
# job makes the two forms safe to run side by side.
export SERVER_SLUG="solo-${SLURM_JOB_ID}"
DISCOVERY="$ROOT/artifacts/servers/${SERVER_SLUG}.json"

# serve_transformers.sh blocks on `wait` after the server is up, so it goes in the
# background and readiness is observed through the advert it publishes. That advert is
# written only after the script's own /health poll AND its fatal identity check that the
# log shows our weights path being loaded -- so its appearance means more than "a port
# is open", and reusing it here keeps that guarantee instead of reimplementing it.
./scripts/serve_transformers.sh &
SERVER_SH_PID=$!

cleanup() {
  local rc=$?
  echo "cleanup: tearing down server (rc=$rc) $(date -Is)"
  # serve_transformers.sh's own EXIT trap kills the server process group and removes the
  # advert; TERM to the script is enough to trigger it.
  kill -TERM "$SERVER_SH_PID" 2>/dev/null
  wait "$SERVER_SH_PID" 2>/dev/null
  rm -f "$DISCOVERY"
  return $rc
}
trap cleanup EXIT INT TERM

# Model load is ~2 min warm; the ceiling is generous because a cold netscratch read of
# 54GB of weights is not.
READY_TIMEOUT=${SOLO_READY_TIMEOUT:-3600}
echo "waiting up to ${READY_TIMEOUT}s for the server advert at $DISCOVERY"
deadline=$((SECONDS + READY_TIMEOUT))
while [ ! -f "$DISCOVERY" ]; do
  if ! kill -0 "$SERVER_SH_PID" 2>/dev/null; then
    echo "server exited before publishing an advert; see artifacts/tf-server-${SLURM_JOB_ID}.log" >&2
    tail -40 "artifacts/tf-server-${SLURM_JOB_ID}.log" 2>/dev/null >&2
    exit 1
  fi
  if (( SECONDS > deadline )); then
    echo "server not ready within ${READY_TIMEOUT}s" >&2
    tail -40 "artifacts/tf-server-${SLURM_JOB_ID}.log" 2>/dev/null >&2
    exit 1
  fi
  sleep 10
done

JQ() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$DISCOVERY" "$1"; }
BASE_URL=$(JQ url)
MODEL="${MODEL:-$(JQ model)}"
echo "server ready: $BASE_URL (model=$MODEL)"

# Same assertion the split form makes before spending wall clock: a run that starts
# against a dead advert produces no-op turns and a log that never names the cause.
curl -fsS --max-time 20 "$BASE_URL/models" >/dev/null \
  || { echo "server at $BASE_URL is not answering" >&2; exit 1; }

# ----------------------------------------------------------------- agent half

export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export JAVA_HOME=${JAVA_HOME:-/usr}

# Per-episode codex home, so the account's global AGENTS.md and personal skills are not
# prepended ahead of this system's prompt every turn (~5-6k tokens of them, measured).
export CODEX_HOME="$ROOT/$OUT/.codexhome"
mkdir -p "$CODEX_HOME"
# The local channel needs no `codex login`: codex authenticates a custom provider from
# env_key, which codex_backend.py sets to LOCAL_API_KEY, and the server does not check
# the value -- but codex refuses to start a provider whose key is unset, so it must exist.
export LOCAL_API_KEY="${LOCAL_API_KEY:-EMPTY}"

# Raised from codex_backend.py's 1800s default, as in worldmodel.sbatch: this path
# decodes at ~5 tok/s, so an 8192-token turn needs ~28 minutes and 1800s cuts it off
# mid-generation, which looks like a hung model and is really a client giving up.
export CODEX_TIMEOUT="${CODEX_TIMEOUT:-3600}"

# The agent is an API-driven coding agent, not a neural policy -- MinecraftSim runs on
# CPU. Masking the GPU keeps its torch from initialising CUDA and reserving memory that
# the server on this same node needs.
export CUDA_VISIBLE_DEVICES=""

PY=$HOME/miniforge3/envs/minestudio/bin/python

# A display number derived from the job id, NOT `xvfb-run -a`. `-a` scans for a free
# display and races: two jobs starting together on one node can pick the same number and
# share an X server, and cancelling either kills Minecraft in the other with a
# "Connection refused" that reads like an agent crash. See worldmodel.sbatch.
DISPLAY_NUM=$(( (SLURM_JOB_ID % 55000) + 200 ))
echo "using display :$DISPLAY_NUM"
echo "agent starting $(date -Is)"

# No srun: the server runs in this batch step's cgroup, and wrapping the agent in a step
# only adds a way for the two to contend over the allocation.
xvfb-run --server-num="$DISPLAY_NUM" -s "-screen 0 1024x768x24" \
  "$PY" -m mcu_worldmodel.run \
    --task "$TASK" \
    --output "$OUT" \
    --model "$MODEL" \
    --effort "${EFFORT:-medium}" \
    --base-url "$BASE_URL" \
    --codex-home "$CODEX_HOME" \
    --induction-every "${INDUCTION_EVERY:-600}" \
    --step-cap "${STEP_CAP:-400}" &
AGENT_PID=$!

# A watchdog, because the failure this form is most exposed to is the server dying under
# a still-running agent. Without it the agent keeps issuing turns that error out and
# burns the remaining wall clock producing nothing -- 22 turns and 8 environment steps
# was the observed shape of that.
#
# Started AFTER the agent, not before: a subshell snapshots the environment at fork, so
# one launched ahead of the assignment would hold an empty AGENT_PID and kill nothing.
( while kill -0 "$SERVER_SH_PID" 2>/dev/null; do sleep 30; done
  echo "server exited; stopping agent" >&2
  kill -TERM "$AGENT_PID" 2>/dev/null ) &
WATCHDOG_PID=$!

wait "$AGENT_PID"
AGENT_RC=$?

kill -TERM "$WATCHDOG_PID" 2>/dev/null
echo "finished=$(date -Is) agent_rc=$AGENT_RC"
exit $AGENT_RC
