#!/usr/bin/env bash
# The three cells of one campaign, detached, against one shared server.
#
#   DRY=1 bash scripts/launch_campaign.sh                 # print, do not run
#   TAG=qwen35_v1 N=300 bash scripts/launch_campaign.sh
#   CELLS="bcp:prolong" bash scripts/launch_campaign.sh   # one cell, or a subset
#
# Concurrency is per cell and deliberately unequal (see scripts/run_cell.sh). The sum is what
# the server sees, so raising one means lowering another -- on the TP=4 server
# (3.04 M-token KV) the defaults below put ~58 requests in flight, against a measured
# ceiling of ~87 BrowseComp-Plus-sized contexts.
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
N="${N:-300}"
CELLS="${CELLS:-bcp:default bcp:hypothesis bcp:prolong}"
DRY="${DRY:-0}"

server_for() {
  # Two servers with *identical* settings are not a difference an arm can see -- same
  # tensor-parallel degree, so the same reduction order, same flags, same weights -- so a
  # comparison may be split across them. Two servers with different TP degrees may not,
  # which is the distinction SERVER_BCP exists to keep. SERVER_BCP_PROLONG
  # peels off the one BrowseComp-Plus arm heavy enough to want a server to itself.
  case "$1" in
    bcp:prolong) echo "${SERVER_BCP_PROLONG:-${SERVER_BCP:-${SERVER_URL:-http://192.168.2.20:8010/v1}}}" ;;
    bcp:*)       echo "${SERVER_BCP:-${SERVER_URL:-http://192.168.2.20:8010/v1}}" ;;
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

concurrency_for() {
  case "$1" in
    bcp:default|bcp:hypothesis)  echo "${C_BCP:-16}" ;;
    # Each episode is a codex process in its own namespace, not just a request.
    bcp:prolong)                 echo "${C_BCP_PROLONG:-8}" ;;
    *)                           echo 1 ;;
  esac
}

RUNNER="$(snapshot_runner)"
echo "runner snapshot: $RUNNER"

for cell in $CELLS; do
  bench="${cell%%:*}"; agent="${cell##*:}"
  c="$(concurrency_for "$cell")"
  out="runs/$TAG/${bench}_${agent}"
  cmd=(env AGENT="$agent" BENCH="$bench" N="$N" TAG="$TAG" CONCURRENCY="$c"
       SERVER_URL="$(server_for "$cell")" bash "$RUNNER")
  if [[ "$DRY" == "1" ]]; then
    printf '%s\n' "${cmd[*]}"
    continue
  fi
  mkdir -p "$out"
  nohup "${cmd[@]}" > "$out/launch.log" 2>&1 &
  echo "launched $cell (concurrency $c, pid $!) -> $out"
  # The BrowseComp-Plus cells each read a 4.2 GB pickle and build nothing; starting
  # them together only makes them contend for the page cache.
  sleep 5
done
