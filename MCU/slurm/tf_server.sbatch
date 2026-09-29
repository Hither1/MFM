#!/usr/bin/env bash
# The Qwen3.8-27B transformers server the world-model agent talks to.
#
#   sbatch slurm/tf_server.sbatch
#
# gpu_h200, not a kempner partition: the kempner_eng QOS caps this account at 16 GPUs and
# the user's own 4-node jobs occupy all of them, so a kempner submission sits in
# QOSMaxGRESPerUser behind work that must not be disturbed.
#
# One H200 (141 GB) for a 27B bf16 model (~54 GB), leaving room for the KV cache of a
# long episode.
#SBATCH -J mcu-tfserve
#SBATCH -p gpu_h200
#SBATCH --gres=gpu:nvidia_h200:1
#SBATCH -c 16
#SBATCH --mem=192G
#SBATCH -t 2-00:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

set -uo pipefail
ROOT=/n/holylfs06/LABS/sham_lab/Users/$USER/MCU
cd "$ROOT"
mkdir -p slurm/logs artifacts/servers

echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

exec ./scripts/serve_transformers.sh
