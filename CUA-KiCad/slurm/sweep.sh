#!/bin/bash
# Submit a memory-search job for each game in a list.
#
# Usage (game ids must exist on the ARC-AGI API; currently ls20 is the LS game):
#   bash slurm/sweep.sh janus  ls20
#   bash slurm/sweep.sh qwen   ls20
#   bash slurm/sweep.sh showo2 ls20
#   bash slurm/sweep.sh blip3o ls20
#   bash slurm/sweep.sh janus  ls20 --no-image-gen   # pass extra args after game list

set -euo pipefail

BACKEND="${1:-janus}"
shift

EXTRA_ARGS=()
GAMES=()
for arg in "$@"; do
    if [[ "$arg" == --* ]]; then
        EXTRA_ARGS+=("$arg")
    else
        GAMES+=("$arg")
    fi
done

if [[ ${#GAMES[@]} -eq 0 ]]; then
    echo "Usage: bash slurm/sweep.sh <janus|qwen|showo2|blip3o> <game1> [game2 ...] [--extra-flags]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for GAME in "${GAMES[@]}"; do
    if [[ "$BACKEND" == "janus" ]]; then
        NO_IMAGE_GEN=""
        for flag in "${EXTRA_ARGS[@]}"; do
            [[ "$flag" == "--no-image-gen" ]] && NO_IMAGE_GEN="--no-image-gen"
        done
        JOB=$(sbatch \
            --export=ALL,GAME="${GAME}",NO_IMAGE_GEN="${NO_IMAGE_GEN}" \
            "${SCRIPT_DIR}/memory_janus.sh")
    elif [[ "$BACKEND" == "showo2" ]]; then
        JOB=$(sbatch \
            --export=ALL,GAME="${GAME}" \
            "${SCRIPT_DIR}/memory_showo2.sh")
    elif [[ "$BACKEND" == "blip3o" ]]; then
        JOB=$(sbatch \
            --export=ALL,GAME="${GAME}" \
            "${SCRIPT_DIR}/memory_blip3o.sh")
    else
        JOB=$(sbatch \
            --export=ALL,GAME="${GAME}" \
            "${SCRIPT_DIR}/memory_qwen.sh")
    fi
    echo "Submitted ${BACKEND} | game=${GAME} → ${JOB}"
done
