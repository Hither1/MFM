#!/usr/bin/env bash
# One long-lived `transformers serve` process that the world-model agent queries.
#
# This is the fallback path, chosen because vLLM cannot run on this cluster at all:
# every CUDA-12 vLLM wheel is manylinux_2_31 or newer and RHEL8 has glibc 2.28, while
# every wheel old enough for that glibc is a CUDA-13 build needing driver >= 580 against
# this cluster's 575. The two constraints do not intersect anywhere in vLLM's release
# history -- see scripts/serve_vllm.sh, kept for the day the driver is upgraded.
#
# Torch, unlike vLLM, ships a CUDA 12.8 build that this driver runs, which is what makes
# this path work where the other does not.
#
# The endpoint codex needs -- POST /v1/responses -- IS registered by transformers 5.9.0
# (cli/serving/server.py:108) even though `transformers serve --help` does not list it.
# Do not "fix" the wire_api to chat on the strength of that help text.
set -uo pipefail

ROOT_DIR=${MCU_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
PYTHON_BIN=${TF_PYTHON:-$HOME/miniforge3/envs/vla/bin/python}
MODEL_ID=${MODEL_ID:-/n/netscratch/sham_lab/Lab/$USER/Qwen3.8-27B}
PORT=${TF_PORT:-$(( 30000 + ${SLURM_JOB_ID:-$$} % 10000 ))}
# sdpa, never flash_attention_2. flash-attn is precompiled against a CUDA runtime this
# driver does not support -- it is the exact kernel that killed all four vLLM attempts.
# sdpa is plain PyTorch and compiles nothing.
ATTN_IMPL=${TF_ATTN_IMPL:-sdpa}
DTYPE=${TF_DTYPE:-bfloat16}
# Paged attention. serve_vllm.sh's header records why the previous generation of this
# path was abandoned -- "a PRO-LONG episode eventually died of allocator fragmentation,
# not capacity" -- and continuous batching is transformers' answer to exactly that. It
# did not exist when that judgement was made. Set TF_CONTINUOUS_BATCHING=0 to fall back
# to the unpaged path if it misbehaves at startup.
CB=${TF_CONTINUOUS_BATCHING:-1}
# Thinking on, matching what serve_vllm.sh pinned and what the finished Qwen3.8 runs
# used. Qwen3.8's card warns that low reasoning effort in multi-turn agentic tasks
# "can lead to insufficient analysis, more failures, and repeated retries".
CHAT_TEMPLATE_KWARGS=${TF_CHAT_TEMPLATE_KWARGS:-'{"enable_thinking": true}'}
SERVER_SLUG=${SERVER_SLUG:-qwen38-27b}
DISCOVERY_DIR=${DISCOVERY_DIR:-$ROOT_DIR/artifacts/servers}
DISCOVERY=$DISCOVERY_DIR/$SERVER_SLUG.json
READY_TIMEOUT=${TF_READY_TIMEOUT:-3600}
LOG=${ART_DIR:-$ROOT_DIR/artifacts}/tf-server-${SLURM_JOB_ID:-local}.log

export PYTHONNOUSERSITE=1
export HF_HOME=${HF_HOME:-/n/netscratch/sham_lab/Lab/$USER/huggingface}
export TOKENIZERS_PARALLELISM=false

mkdir -p "$DISCOVERY_DIR" "$(dirname "$LOG")"
HOST_FQDN=$(hostname -s)

# Fail named and immediately if the serving extra is missing, rather than 60 seconds
# into a startup crash.
if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, transformers.cli.serving.server" >/dev/null 2>&1; then
  echo "serving env is incomplete (needs transformers[serving]: fastapi + uvicorn):" >&2
  "$PYTHON_BIN" -c "import fastapi, uvicorn, transformers.cli.serving.server" 2>&1 | tail -5 >&2
  exit 1
fi

cleanup() {
  if [[ -f $DISCOVERY ]] && grep -q "\"job\": \"${SLURM_JOB_ID:-none}\"" "$DISCOVERY" 2>/dev/null; then
    rm -f "$DISCOVERY"
  fi
  [[ -n ${SERVER_PGID:-} ]] && kill -TERM -- "-$SERVER_PGID" 2>/dev/null
  true
}
trap cleanup EXIT INT TERM

CB_FLAG=$( [ "$CB" = 1 ] && echo --continuous-batching || echo --no-continuous-batching )
echo "starting transformers serve: $MODEL_ID on $HOST_FQDN:$PORT" \
     "(attn=$ATTN_IMPL dtype=$DTYPE cb=$CB thinking=$CHAT_TEMPLATE_KWARGS)"

# The model is passed as FORCE_MODEL (the positional), which preloads it and uses it for
# EVERY request regardless of the model name the client sends. That is what lets codex
# ask for "qwen3.8-27b" while the server knows the weights only by their directory path.
setsid "$PYTHON_BIN" "$ROOT_DIR/scripts/serve_qwen_for_codex.py" serve "$MODEL_ID" \
  --host 0.0.0.0 --port "$PORT" \
  --attn-implementation "$ATTN_IMPL" \
  --dtype "$DTYPE" \
  --device auto \
  --trust-remote-code \
  --chat-template-kwargs "$CHAT_TEMPLATE_KWARGS" \
  $CB_FLAG \
  > "$LOG" 2>&1 &
SERVER_PID=$!
SERVER_PGID=$SERVER_PID

deadline=$((SECONDS + READY_TIMEOUT))
while true; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "transformers serve exited before becoming ready; see $LOG" >&2
    tail -40 "$LOG" >&2
    exit 1
  fi
  curl -fsS "http://127.0.0.1:$PORT/health" > /dev/null 2>&1 && break
  if (( SECONDS > deadline )); then
    echo "server not ready within ${READY_TIMEOUT}s; see $LOG" >&2
    tail -40 "$LOG" >&2
    exit 1
  fi
  sleep 10
done

# The name in the advert is OURS, not the one /v1/models reports.
#
# transformers serve's /v1/models returns a default catalog entry -- observed as
# "Qwen/Qwen3-4B-Instruct-2507" -- which has nothing to do with the force-loaded weights.
# Trusting it wrote a 4B model's name into a 27B run's advert, which is the precise
# failure serve_vllm.sh's identity assertion exists to prevent: a run that records the
# wrong model produces numbers under the wrong name, worse than one that fails to start.
#
# The name is NOT free to choose. FORCE_MODEL pins the server and *validates* the
# requested name against it, rejecting anything else:
#
#   {"detail":"Server is pinned to '/n/netscratch/.../Qwen3.8-27B'; requested 'qwen3.8-27b'."}
#
# so the advertised model must be the weights path verbatim -- that is the only string
# the server answers to. Which is no loss: a path is stronger provenance than a label,
# since it names the exact directory that produced the numbers. The human-readable name
# rides along as "label" for reports.
#
# What is asserted below, fatally, is that the server log shows OUR weights path being
# loaded, because /v1/models cannot be trusted to say.
# The one string the pinned server accepts.
SERVED_NAME=${SERVED_NAME:-$MODEL_ID}
LABEL=${SERVER_LABEL:-qwen3.8-27b}
CATALOG=$(curl -fsS "http://127.0.0.1:$PORT/v1/models" 2>/dev/null \
  | "$PYTHON_BIN" -c 'import json,sys
try:
    d=json.load(sys.stdin).get("data") or []
    print(d[0]["id"] if d else "")
except Exception:
    print("")')
# Fatal identity check, against the log, which records the real load.
if ! grep -q "Loading ${MODEL_ID}" "$LOG" 2>/dev/null; then
  echo "server did not load ${MODEL_ID}; refusing to advertise it" >&2
  grep -iE "Loading /" "$LOG" 2>/dev/null | head -3 >&2
  exit 1
fi
echo "verified loaded weights: $MODEL_ID (advertised as $SERVED_NAME; catalog says '${CATALOG:-<empty>}')"
SERVED="$SERVED_NAME"

cat > "$DISCOVERY.tmp" <<JSON
{
  "url": "http://$HOST_FQDN:$PORT/v1",
  "host": "$HOST_FQDN",
  "port": $PORT,
  "model": "$SERVED",
  "label": "$LABEL",
  "models_endpoint_catalog": "$CATALOG",
  "weights": "$MODEL_ID",
  "backend": "transformers-serve",
  "attn_implementation": "$ATTN_IMPL",
  "dtype": "$DTYPE",
  "continuous_batching": $( [ "$CB" = 1 ] && echo true || echo false ),
  "chat_template_kwargs": $CHAT_TEMPLATE_KWARGS,
  "job": "${SLURM_JOB_ID:-none}",
  "started_at": "$(date -Iseconds)"
}
JSON
mv "$DISCOVERY.tmp" "$DISCOVERY"
echo "server ready and advertised: $DISCOVERY"
cat "$DISCOVERY"

wait "$SERVER_PID"
