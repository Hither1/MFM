#!/bin/bash
# One KiCad results cell: gym_codex/run_eval.py on cua.bench.local.kicad in the wave setup
# (project-dir hint, one task at a time, all 25 tasks unless --tasks is passed).
#
# usage: WORK=<dir> [PROVIDER=openrouter|claude] scripts/run_kicad_arm.sh AGENT MODEL EFFORT OUT_DIR [run_eval args...]
#
# WORK holds shim/docker, codex-node-0.153/, codex-eval-home/ and (by default) cua-lite/.
# PROVIDER unset = the ChatGPT account logged in under $WORK/codex-eval-home;
# PROVIDER=openrouter = codex against OpenRouter with $OPENROUTER_API_KEY.
# PROVIDER=claude = Claude Code on a Claude subscription (--cli claude; direct/prolong*/mfm*):
#   CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`, or CLAUDE_EVAL_AUTH=<.credentials.json>.
# Step-by-step: docs/KICAD_RUNS.md.
set -euo pipefail
: "${WORK:?set WORK (see docs/KICAD_RUNS.md)}"
[ $# -ge 4 ] || { sed -n '5,11p' "$0"; exit 2; }
KICAD=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MFM=${MFM_ROOT:-$(cd "$KICAD/.." && pwd)}
LITE=${CUA_LITE_ROOT:-$WORK/cua-lite}
AGENT=$1 MODEL=$2 EFFORT=$3 OUT=$4; shift 4

export PATH=$WORK/shim:$WORK/codex-node-0.153/bin:$PATH
export CODEX_NODE_DIR=$WORK/codex-node-0.153
export CODEX_EVAL_HOME=$WORK/codex-eval-home
export CODEX_SANDBOX_INNER_PYTHON=$(command -v python3)
unset CODEX_HOME
# The memory arms run codex inside the bubblewrap sandbox; the direct arm runs it bare.
if [ "$AGENT" != direct ]; then
    export CODEX_BIN=$KICAD/prolong_search/codex_sandbox.sh
fi
CLI_ARGS=()

if [ "${PROVIDER:-hosted}" = openrouter ]; then
    : "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
    export LOCAL_API_KEY=$OPENROUTER_API_KEY
    export CODEX_BASE_URL=https://openrouter.ai/api/v1
    export CODEX_SANDBOX_ALLOW=openrouter.ai:443
    export CODEX_SANDBOX_NO_AUTH=1
elif [ "${PROVIDER:-hosted}" = claude ]; then
    # The memory arms run claude inside claude_sandbox.sh (reads confined to the
    # workspace, egress only to Anthropic); the direct arm has no tools and runs it bare.
    [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || [ -r "${CLAUDE_EVAL_AUTH:-$HOME/.claude-eval/.credentials.json}" ] || {
        echo "PROVIDER=claude: export CLAUDE_CODE_OAUTH_TOKEN (claude setup-token) or CLAUDE_EVAL_AUTH" >&2; exit 2; }
    export CLAUDE_REAL_BIN=${CLAUDE_REAL_BIN:-$(command -v claude)}
    if [ "$AGENT" != direct ]; then
        export CLAUDE_BIN=$KICAD/prolong_search/claude_sandbox.sh
        export CLAUDE_SANDBOX_INNER_PYTHON=$CODEX_SANDBOX_INNER_PYTHON
    else
        export CLAUDE_BIN=$CLAUDE_REAL_BIN
    fi
    CLI_ARGS=(--cli claude)
fi

# Node-local podman storage and a private network namespace per container
# (scripts/podman-docker-shim reads these).
PODROOT=${TMPDIR:-/tmp}/$USER-podman-${SLURM_JOB_ID:-$$}
mkdir -p "$PODROOT/root" "$PODROOT/run"
export PODMAN_ROOT=$PODROOT/root PODMAN_RUNROOT=$PODROOT/run
export PODMAN_NETWORK=slirp4netns PODMAN_SHM_SIZE=2g
trap 'docker ps -aq 2>/dev/null | xargs -r docker rm -f >/dev/null 2>&1; rm -rf "$PODROOT"' EXIT
docker image exists trycua/cua-xfce:latest || {
    docker pull docker.io/trycua/cua-xfce:latest
    docker tag docker.io/trycua/cua-xfce:latest trycua/cua-xfce:latest
}

cd "$LITE"
PYTHONPATH=$MFM:${PYTHONPATH:-} .venv/bin/python "$KICAD/gym_codex/run_eval.py" \
    --env-id cua.bench.local.kicad --model "$MODEL" --effort "$EFFORT" \
    --concurrency 1 --agent "$AGENT" --out "$OUT" --kicad-project-hint "${CLI_ARGS[@]}" "$@"
