#!/usr/bin/env bash
# One shard of the PRO-LONG BrowseComp-Plus cell, against one server.
#
#   SHARD=0/2 SERVER_URL=http://192.168.2.20:8011/v1 CONCURRENCY=20 \
#   CODEX_TIMEOUT=360 TAG=qwen35_v2 N=830 bash scripts/run_shard.sh
#
# Separate from run_cell.sh only because that file is being read, byte by byte, by a
# cell that is still running (see the snapshot note in launch_campaign.sh); fold this
# back in once nothing is executing it.
#
# **Why a ceiling this much lower than the 1800 s default.** Measured on the first
# attempt at this cell: 169 of ~1100 analyzer turns ran to the 1800 s ceiling, evenly
# spread over ten hours -- a steady ~30 % of turns, which is the same unbounded-generation
# pathology the MineExplorer campaign measured on its codex arm. They consumed 43 % of the
# arm's compute and pushed the median episode to 66 minutes. A turn that answers takes
# ~150 s here, so 360 s keeps the answers and cuts the runaways at a fifth of the price.
# It is a change to what the arm scores, so it is recorded in `result.json` as
# `codex_timeout_s` and the run it replaces is kept beside it.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

SHARD="${SHARD:?SHARD must be K/N}"
N="${N:-830}"
TAG="${TAG:-qwen35_v2}"
PY="${PY:-/datapool/data3/storage/ruihan/data_share/jh/Collab/venvs/qwen35/bin/python}"
SERVER_URL="${SERVER_URL:?SERVER_URL must be set}"
SERVER_MODEL="${SERVER_MODEL:-Qwen3.5-27B}"
CONCURRENCY="${CONCURRENCY:-20}"
CODEX_EFFORT="${CODEX_EFFORT:-low}"   # thinking on; see run_cell.sh
export CODEX_TIMEOUT="${CODEX_TIMEOUT:-360}"

SLUG="${SHARD//\//of}"
OUT="$REPO/runs/$TAG/bcp_prolong"
mkdir -p "$OUT"
date +%s > "$OUT/started_at.$SLUG"

hostport="${SERVER_URL#http://}"; hostport="${hostport%%/*}"
export CODEX_BIN="${CODEX_BIN:-$REPO/prolong_search/codex_sandbox.sh}"
export CODEX_EVAL_HOME="${CODEX_EVAL_HOME:-$HOME/.codex-eval}"
export CODEX_SANDBOX_ALLOW="${CODEX_SANDBOX_ALLOW:-$hostport}"
export CODEX_SANDBOX_NO_AUTH="${CODEX_SANDBOX_NO_AUTH:-1}"

echo "=== bcp:prolong shard $SHARD  n=$N  concurrency=$CONCURRENCY  ceiling=${CODEX_TIMEOUT}s  server=$SERVER_URL"
exec > >(tee -a "$OUT/stdout.$SLUG.log") 2>&1
"$PY" eval_prolong_browsecomp_plus.py \
  --limit "$N" --concurrency "$CONCURRENCY" --shard "$SHARD" \
  --codex-model "$SERVER_MODEL" --codex-base-url "$SERVER_URL" \
  --codex-effort "$CODEX_EFFORT" \
  --judge local --server-url "$SERVER_URL" --server-model "$SERVER_MODEL" \
  --data-cache-dir data/browsecomp_plus \
  --workspace-root "$OUT/workspace.$SLUG" \
  --output "$OUT/result.$SLUG.json"
