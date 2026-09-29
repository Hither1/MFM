#!/bin/bash
#SBATCH --job-name=arc-extract-targets
#SBATCH --partition=kempner_requeue
#SBATCH --account=kempner_sham_lab
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=logs/extract_targets_%j.out
#SBATCH --error=logs/extract_targets_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=csu@g.harvard.edu

# Download game files and extract target grids for all 25 ARC-AGI 3 games.
# Usage:
#   sbatch slurm/extract_targets.sh
#   sbatch --export=ALL,GAMES="ls20 cd82" slurm/extract_targets.sh  # subset

ALL_GAMES="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
GAMES="${GAMES:-$ALL_GAMES}"

# Submit from the repo root: logs/ above and this cd are relative to it.
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
source ~/.bashrc
conda activate vla

echo "========================================"
echo "Extracting targets for games: $GAMES"
echo "========================================"

python extract_targets.py \
    --games $GAMES \
    --output-dir target_grids \
    2>&1

echo ""
echo "========================================"
echo "Final cache state:"
python extract_targets.py --list-cached
