#!/usr/bin/env bash
# One campaign cell -- (agent x benchmark) at one n, against one served model.
#
# The three axes stay separate here exactly as README.md describes them: AGENT is
# which evaluator, the channel is fixed per agent (default/hypothesis go straight at
# the server, prolong only exists inside the Codex CLI), and BENCH is the task. What
# this file adds is the fourth thing a cell needs and none of the evaluators know:
# where the shared server is, how many questions may be in flight at once, and where
# the run's evidence goes.
#
#   AGENT=default BENCH=bcp N=300 bash scripts/run_cell.sh
#   AGENT=prolong BENCH=bcp N=300 CONCURRENCY=5 bash scripts/run_cell.sh
#
# CONCURRENCY is a wall-clock knob: every BrowseComp-Plus arm scopes memory to one
# question, so running questions at once changes the clock and nothing else.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

AGENT="${AGENT:?AGENT must be default|hypothesis|prolong}"
BENCH="${BENCH:?BENCH must be bcp}"
N="${N:-300}"
TAG="${TAG:-qwen35_v1}"
PY="${PY:-/datapool/data3/storage/ruihan/data_share/jh/Collab/venvs/qwen35/bin/python}"
SERVER_URL="${SERVER_URL:-http://192.168.2.20:8010/v1}"
SERVER_MODEL="${SERVER_MODEL:-Qwen3.5-27B}"
MODEL_KEY="${MODEL_KEY:-qwen3.5-27b}"
CONCURRENCY="${CONCURRENCY:-8}"
# Not "none". On a local server codex's reasoning.effort is nothing but the thinking
# switch -- vLLM turns `effort != "none"` into enable_thinking -- and it rides on every
# Responses request, so it overrides whatever the server's --default-chat-template-kwargs
# says. The direct arms are pinned thinking-on server-side; this is the same pin for the
# codex arms, and the two have to agree or the channel axis stops being a control.
CODEX_EFFORT="${CODEX_EFFORT:-low}"

OUT="$REPO/runs/$TAG/${BENCH}_${AGENT}"
mkdir -p "$OUT"
LOG="$OUT/stdout.log"
# When this cell started, written once. A checkpoint's ctime is not it -- on Linux
# that is the inode change time and every append moves it -- and under concurrency the
# records' own elapsed_sec overlap, so neither can give a rate. scripts/campaign_status.py
# reads this.
date +%s > "$OUT/started_at"
# ...and how many questions were already in the checkpoint, so a resumed cell's rate is
# measured over the work this process actually did rather than over the whole file.
wc -l < "$OUT/result.checkpoint.jsonl" 2>/dev/null > "$OUT/resumed_from" || echo 0 > "$OUT/resumed_from"

# The codex arms reach the model through the sandbox, and the sandbox has to be told
# that the local server is the one host it may talk to. Without CODEX_BIN the wrapper
# is bypassed and the agent can read this repository -- including the gold answers.
codex_env() {
  local hostport="${SERVER_URL#http://}"; hostport="${hostport%%/*}"
  export CODEX_BIN="${CODEX_BIN:-$REPO/prolong_search/codex_sandbox.sh}"
  export CODEX_EVAL_HOME="${CODEX_EVAL_HOME:-$HOME/.codex-eval}"
  export CODEX_SANDBOX_ALLOW="${CODEX_SANDBOX_ALLOW:-$hostport}"
  export CODEX_SANDBOX_NO_AUTH="${CODEX_SANDBOX_NO_AUTH:-1}"
}

echo "=== cell $BENCH:$AGENT  n=$N  concurrency=$CONCURRENCY  server=$SERVER_URL" | tee "$LOG"

case "$BENCH:$AGENT" in
  bcp:default|bcp:hypothesis)
    script="eval_direct_browsecomp_plus.py"
    [[ "$AGENT" == hypothesis ]] && script="eval_hypothesis_browsecomp_plus.py"
    exec > >(tee -a "$LOG") 2>&1
    "$PY" "$script" \
      --model "$MODEL_KEY" --limit "$N" \
      --server-url "$SERVER_URL" --server-model "$SERVER_MODEL" \
      --concurrency "$CONCURRENCY" \
      --data-cache-dir data/browsecomp_plus \
      --output "$OUT/result.json"
    ;;
  bcp:prolong)
    codex_env
    exec > >(tee -a "$LOG") 2>&1
    "$PY" eval_prolong_browsecomp_plus.py \
      --limit "$N" --concurrency "$CONCURRENCY" \
      --codex-model "$SERVER_MODEL" --codex-base-url "$SERVER_URL" \
      --codex-effort "$CODEX_EFFORT" \
      --judge local --server-url "$SERVER_URL" --server-model "$SERVER_MODEL" \
      --data-cache-dir data/browsecomp_plus \
      --workspace-root "$OUT/workspace" \
      --output "$OUT/result.json"
    ;;
  *) echo "run_cell: unknown cell '$BENCH:$AGENT'" >&2; exit 2 ;;
esac
