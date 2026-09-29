#!/usr/bin/env bash
# The Qwen3.8-27B server the world-model agent talks to.
#
#   sbatch slurm/vllm_server.sbatch
#
# kempner_h200 rather than kempner_requeue: the agent job holds a single Minecraft
# episode with no checkpoint, so a preemption partway through does not cost a requeue,
# it costs the episode. The 2-day limit is the partition's ceiling and is well clear of
# the agent's 24h.
#
# One GPU. An H200 is 141 GB; 27B in bf16 is ~54 GB, leaving the rest for the KV cache
# at 131k context. See scripts/serve_vllm.sh for why TP=1 is the right default here and
# was not on the cluster this recipe came from.
#SBATCH -J mcu-vllm
#SBATCH -p kempner_h200
#SBATCH -A kempner_sham_lab
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

exec ./scripts/serve_vllm.sh
