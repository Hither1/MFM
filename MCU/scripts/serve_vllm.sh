#!/usr/bin/env bash
# One long-lived vLLM server that the world-model agent queries.
#
# Adapted from MineExplorer's scripts/serve_vllm.sh, which is where the non-obvious
# settings below were established and measured. The differences from that copy are all
# site differences -- FASRC H200s rather than Delta GH200s, and a model that is already
# on netscratch rather than one pulled from the hub:
#
#  * MODEL_ID is a local directory, so there is no --revision to pin. The identity
#    assertion below therefore checks the served *name*, and the advert records the
#    directory, which is what "which weights answered" means here.
#  * TP defaults to 1. An H200 is 141 GB and 27B in bf16 is ~54 GB, so one card holds
#    the weights with room for the KV cache. MineExplorer used TP=2 to buy decode
#    latency on Grace, where per-kernel launch cost dominates; on x86 H200 the launch
#    overhead is far smaller and a second card mostly buys all-reduce traffic.
#  * The pip-installed NVIDIA runtime libs have to go on LD_LIBRARY_PATH explicitly or
#    `import vllm` fails with "libcudart.so.NN: cannot open shared object file".
#
# The server publishes host and port to a discovery file, because the agent job runs on
# a CPU partition on another node: MinecraftSim's JVM environment is verified on
# sapphire and there is no reason to move it onto a GPU node just to shorten a URL.
set -uo pipefail

ROOT_DIR=${MCU_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
PYTHON_BIN=${VLLM_PYTHON:-/n/home13/chloe00/miniforge3/envs/vla/bin/python}
MODEL_ID=${MODEL_ID:-/n/netscratch/sham_lab/Lab/chloe00/Qwen3.8-27B}
SERVED_NAME=${SERVED_NAME:-qwen3.8-27b}
# 30000-39999: disjoint from the Minecraft sandbox's port range, because a shared node
# may run several jobs.
PORT=${VLLM_PORT:-$(( 30000 + ${SLURM_JOB_ID:-$$} % 10000 ))}
MAX_LEN=${VLLM_MAX_MODEL_LEN:-131072}
GPU_FRAC=${VLLM_GPU_FRACTION:-0.90}
# Qwen3.8 emits XML tool calls -- <tool_call><function=name><parameter=p>value -- not
# Hermes JSON, so `qwen3_xml` is the parser that turns them into structured tool_calls.
# Without it vLLM returns raw text, codex sees no tool call, and the agent silently
# cannot act: a failure that looks like a bad model rather than a missing flag.
TOOL_PARSER=${VLLM_TOOL_PARSER:-qwen3_xml}
# Triton, not vLLM's default FlashAttention.
#
# This is the FASRC-specific setting, and it is not a preference -- FLASH_ATTN cannot run
# here at all. vLLM ships vllm-flash-attn as *prebuilt* Hopper (FA3) kernels compiled in
# its release container against a newer CUDA runtime than this cluster's driver
# (575.57.08) provides, so the engine dies right after the weights land:
#
#   CUDA error (vllm-flash-attn-src/hopper/flash_fwd_launch_template.h:171):
#   CUDA driver version is insufficient for CUDA runtime version
#
# Note the failure is narrow. The 51 GiB of weights load and ordinary CUDA works; only
# the prebuilt attention kernel is mismatched. This is the same wall the sibling
# mllm-search port hit and recorded as "vLLM's precompiled kernels fail on this
# cluster's H100 nodes regardless of vllm/torch version" -- true, but it reads as though
# no vLLM configuration works, which is what sent that project to a transformers
# backend. The narrower reading has a fix: Triton compiles its kernels at runtime
# against the driver actually present, so there is no build-vs-driver skew to mismatch.
#
# FLASHINFER is the other JIT-capable option if Triton ever fails on a hybrid model's
# page-size constraints (the log line to watch is "Setting attention block size to N
# tokens to ensure that attention page size is >= mamba page size").
# Passed as --attention-backend, not as the VLLM_ATTENTION_BACKEND environment variable:
# that variable was removed in vLLM 0.22 and exporting it now does nothing at all, which
# is the quietest possible way to think you have changed a backend and not have.
ATTN_BACKEND=${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}
# The vision tower picks its attention backend SEPARATELY, and --attention-backend does
# not reach it. Setting only that flag moves the language model and leaves the ViT on
# FlashAttention, which fails identically -- the log shows both decisions and they
# disagree:
#
#   [cuda.py:433] Using backend AttentionBackendEnum.FLASH_ATTN for vit attention
#   [cuda.py:318] Using AttentionBackendEnum.TRITON_ATTN backend.
#
# and the crash then lands in the profiling run, which forwards "1 image items" through
# the tower. This matters here specifically because the agent attaches a frame to every
# turn: a text-only model on this cluster would never touch the broken path.
#
# TORCH_SDPA rather than Triton for the tower. It is plain PyTorch with no custom kernel
# to mismatch, and the tower runs once per attached frame -- next to 27B of decode its
# cost does not show up. Triton would probably work too; this trades a little speed for
# not spending another startup to find out.
MM_ATTN_BACKEND=${VLLM_MM_ATTENTION_BACKEND:-TORCH_SDPA}
EAGER=${VLLM_EAGER:-0}
# Every decode sequence holds one Mamba cache block for its recurrent state, so graph
# capture refuses to run unless max_num_seqs fits the blocks the KV budget bought.
# vLLM's default of 1024 makes capture impossible on this architecture.
MAX_NUM_SEQS=${VLLM_MAX_NUM_SEQS:-32}
TP=${VLLM_TP:-1}
# The codex path cannot ask for an output cap -- it ignores max_tokens by design -- so
# the server is the only place to set one. 16384 clears what this model actually emits
# with thinking on (p90 1933, largest observed single message 12,918 tokens) while still
# foreclosing a runaway generating toward the 131k context end.
MAX_OUTPUT_TOKENS=${VLLM_MAX_OUTPUT_TOKENS:-16384}
# Qwen3.8's own thinking-mode recipe, pinned on the server because the codex channel
# sends no sampling parameters at all.
SAMPLING=${VLLM_SAMPLING:-'"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0'}
# Thinking on. Qwen3.8 defaults to it and its card warns that low reasoning effort in
# multi-turn agentic tasks "can lead to insufficient analysis, more failures, and
# repeated retries" -- which MineExplorer measured directly: with thinking off an arm
# looped on `echo ok` 87 times inside one call and burned the client timeout.
CHAT_TEMPLATE_KWARGS=${VLLM_CHAT_TEMPLATE_KWARGS:-'{"enable_thinking": true}'}
SERVER_SLUG=${SERVER_SLUG:-qwen38-27b}
DISCOVERY_DIR=${DISCOVERY_DIR:-$ROOT_DIR/artifacts/servers}
DISCOVERY=$DISCOVERY_DIR/$SERVER_SLUG.json
READY_TIMEOUT=${VLLM_READY_TIMEOUT:-2400}
LOG=${ART_DIR:-$ROOT_DIR/artifacts}/vllm-server-${SLURM_JOB_ID:-local}.log

CONDA_ENV_LIB=$(dirname "$(dirname "$PYTHON_BIN")")/lib
NVIDIA_LIB="$CONDA_ENV_LIB/python3.11/site-packages/nvidia/cu13/lib"
export LD_LIBRARY_PATH="$CONDA_ENV_LIB:$NVIDIA_LIB:${LD_LIBRARY_PATH:-}"
export HF_HOME=${HF_HOME:-/n/netscratch/sham_lab/Lab/chloe00/huggingface}
export PYTHONNOUSERSITE=1
export VLLM_LOGGING_LEVEL=${VLLM_LOGGING_LEVEL:-INFO}

mkdir -p "$DISCOVERY_DIR" "$(dirname "$LOG")"
HOST_FQDN=$(hostname -s)

# Import the model module before starting vLLM, under the same environment the server
# runs in. A dependency installed into the *user* site-packages is invisible under
# PYTHONNOUSERSITE=1, so it passes a casual login-node check and then fails on the node.
# Checking here turns a 60-second startup crash into an immediate, named failure.
if ! "$PYTHON_BIN" -c "import vllm.model_executor.models.qwen3_5" >/dev/null 2>&1; then
  echo "serving env cannot import the model module (deps missing under PYTHONNOUSERSITE=1):" >&2
  "$PYTHON_BIN" -c "import vllm.model_executor.models.qwen3_5" 2>&1 | tail -6 >&2
  exit 1
fi

cleanup() {
  # Remove our own advert only. A stale discovery file pointing at a dead node is
  # exactly how a run ends up scoring against nothing.
  if [[ -f $DISCOVERY ]] && grep -q "\"job\": \"${SLURM_JOB_ID:-none}\"" "$DISCOVERY" 2>/dev/null; then
    rm -f "$DISCOVERY"
  fi
  [[ -n ${SERVER_PGID:-} ]] && kill -TERM -- "-$SERVER_PGID" 2>/dev/null
  true
}
trap cleanup EXIT INT TERM

echo "starting vLLM: $MODEL_ID on $HOST_FQDN:$PORT (max_len=$MAX_LEN tp=$TP attn=$ATTN_BACKEND vit=$MM_ATTN_BACKEND" \
     "exec=$( [ "$EAGER" = 1 ] && echo eager || echo cudagraphs ) max_out=$MAX_OUTPUT_TOKENS" \
     "chat_template_kwargs=$CHAT_TEMPLATE_KWARGS)"
setsid "$PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_ID" \
  --served-model-name "$SERVED_NAME" \
  --host 0.0.0.0 --port "$PORT" \
  --max-model-len "$MAX_LEN" \
  --tensor-parallel-size "$TP" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --gpu-memory-utilization "$GPU_FRAC" \
  --trust-remote-code \
  --attention-backend "$ATTN_BACKEND" \
  --mm-encoder-attn-backend "$MM_ATTN_BACKEND" \
  --enable-auto-tool-choice --tool-call-parser "$TOOL_PARSER" \
  --override-generation-config "{\"max_new_tokens\": $MAX_OUTPUT_TOKENS, $SAMPLING}" \
  --default-chat-template-kwargs "$CHAT_TEMPLATE_KWARGS" \
  $( [ "$EAGER" = 1 ] && echo --enforce-eager || echo -cc.mode=none -cc.cudagraph_mode=FULL_DECODE_ONLY ) \
  > "$LOG" 2>&1 &
SERVER_PID=$!
SERVER_PGID=$SERVER_PID

deadline=$((SECONDS + READY_TIMEOUT))
while true; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "vLLM exited before becoming ready; see $LOG" >&2
    tail -40 "$LOG" >&2
    exit 1
  fi
  curl -fsS "http://127.0.0.1:$PORT/v1/models" > /dev/null 2>&1 && break
  if (( SECONDS > deadline )); then
    echo "vLLM not ready within ${READY_TIMEOUT}s; see $LOG" >&2
    tail -40 "$LOG" >&2
    exit 1
  fi
  sleep 10
done

# Assert the server is serving what we asked for before advertising it. A run that
# discovers the wrong model produces numbers under the wrong name, which is worse than
# a run that fails to start.
SERVED=$(curl -fsS "http://127.0.0.1:$PORT/v1/models" | "$PYTHON_BIN" -c \
  'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])')
if [[ "$SERVED" != "$SERVED_NAME" ]]; then
  echo "server reports model '$SERVED', expected '$SERVED_NAME'" >&2
  exit 1
fi

# The serving configuration travels with the advert, not just the URL. The output cap
# and the thinking pin change what the model produces, so "which server answered" has to
# be answerable months later from the run's own artifacts.
cat > "$DISCOVERY.tmp" <<JSON
{
  "url": "http://$HOST_FQDN:$PORT/v1",
  "host": "$HOST_FQDN",
  "port": $PORT,
  "model": "$SERVED_NAME",
  "weights": "$MODEL_ID",
  "max_model_len": $MAX_LEN,
  "max_output_tokens": $MAX_OUTPUT_TOKENS,
  "sampling": {$SAMPLING},
  "tensor_parallel_size": $TP,
  "attention_backend": "$ATTN_BACKEND",
  "mm_encoder_attn_backend": "$MM_ATTN_BACKEND",
  "execution": "$( [ "$EAGER" = 1 ] && echo eager || echo cudagraphs-full-decode-only )",
  "chat_template_kwargs": $CHAT_TEMPLATE_KWARGS,
  "job": "${SLURM_JOB_ID:-none}",
  "started_at": "$(date -Iseconds)"
}
JSON
mv "$DISCOVERY.tmp" "$DISCOVERY"
echo "vLLM ready and advertised: $DISCOVERY"
cat "$DISCOVERY"

# Stay alive for the allocation; the agent job comes and goes against this process.
wait "$SERVER_PID"
