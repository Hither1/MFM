#!/usr/bin/env bash
# Photograph the dragon task's endgame milestones. CPU only -- no policy runs here, just
# the engine, server commands and the renderer.
#
#   sbatch slurm/endgame_frames.sbatch [output-dir] [stages]
#
#SBATCH -J mcu-endgame-frames
#SBATCH -p sapphire
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 3:00:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err
set -uo pipefail

ROOT=/n/holylfs06/LABS/sham_lab/Users/chloe00/MCU
cd "$ROOT" || exit 1
mkdir -p slurm/logs

OUT=${1:-output/endgame_frames_$SLURM_JOB_ID}
STAGES=${2:-nether,blaze_powder,end}
mkdir -p "$OUT"

echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="
echo "out=$OUT stages=$STAGES"
java -version 2>&1 | head -1

export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
export CUDA_VISIBLE_DEVICES=""
unset MINESTUDIO_GPU_RENDER
PY=$HOME/miniforge3/envs/minestudio/bin/python

# Display number from the job id rather than `xvfb-run -a`; see solo.sbatch.
DISPLAY_NUM=$(( (SLURM_JOB_ID % 55000) + 200 ))
xvfb-run --server-num="$DISPLAY_NUM" -s "-screen 0 1024x768x24" \
  "$PY" scripts/dragon_endgame_frames.py --out "$OUT" --stages "$STAGES"
echo "exit=$? $(date -Is)"
ls "$OUT/frames" | head -50
