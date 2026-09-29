#!/usr/bin/env bash
# Take a finished n=300 campaign to the full benchmark (BrowseComp-Plus 830).
#
#   DRY=1 bash scripts/launch_full.sh
#   TAG=qwen35_v1 bash scripts/launch_full.sh
#
# **Every cell resumes.** BrowseComp-Plus scopes memory to one question in all three of
# its arms, so extending `--limit` re-reads the checkpoint and simply carries on: the
# questions already answered were answered under exactly the conditions they would
# have been. (An arm whose memory spans the run could not be extended this way; it
# would have to start fresh in its own tag.)
# **One server per benchmark, never per arm.** The three arms of a benchmark are what get
# compared, so they must see the same server: tensor-parallel degree changes the order of
# the all-reduce reductions, which at temperature 0.7 can flip a token, and prefix caching
# already puts the mamba layers in chunk-aligned prefill. Splitting a comparison across two
# servers would put that difference inside it. SERVER_BCP selects it; each result.json
# records the endpoint it ran against.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

TAG="${TAG:-qwen35_v1}"
N_BCP="${N_BCP:-830}"
DRY="${DRY:-0}"

server_for() {
  case "${1%%:*}" in
    bcp)      echo "${SERVER_BCP:-${SERVER_URL:-http://192.168.2.20:8010/v1}}" ;;
  esac
}

# **Cells run a snapshot of run_cell.sh, not run_cell.sh.** bash reads a script by byte
# offset as it executes it, so editing the file under a running cell makes it resume at
# the wrong place -- measured 2026-08-19: a cell that had already written its result.json
# came back with `run_cell.sh: line 123: model: command not found` when its python exited,
# because the file had grown by two lines mid-run. The snapshot lives in scripts/ so that
# run_cell.sh's own `dirname $BASH_SOURCE/..` still resolves to the repository.
snapshot_runner() {
  local snap="scripts/.run_cell.${TAG}.$(date +%Y%m%dT%H%M%S).sh"
  cp scripts/run_cell.sh "$snap"
  echo "$snap"
}

run() {                       # run <tag> <bench> <agent> <n> <concurrency>
  local cmd=(env AGENT="$3" BENCH="$2" N="$4" TAG="$1" CONCURRENCY="$5"
             SERVER_URL="$(server_for "$2")" bash "$RUNNER")
  if [[ "$DRY" == "1" ]]; then printf '%s\n' "${cmd[*]}"; return; fi
  local out="runs/$1/$2_$3"; mkdir -p "$out"
  nohup "${cmd[@]}" > "$out/launch.log" 2>&1 &
  echo "launched $2:$3 n=$4 concurrency=$5 -> $out (pid $!)"
  sleep 5
}

RUNNER="$(snapshot_runner)"
echo "runner snapshot: $RUNNER"

echo "== resuming in $TAG (memory is per question; the n=300 records stand) =="
run "$TAG" bcp default    "$N_BCP"      "${C_BCP:-6}"
run "$TAG" bcp hypothesis "$N_BCP"      "${C_BCP:-6}"
run "$TAG" bcp prolong    "$N_BCP"      "${C_BCP_PROLONG:-5}"
