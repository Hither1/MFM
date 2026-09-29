#!/bin/bash
# Install missing dependencies into the base conda environment (Python 3.12).
# Run once on a login node (no GPU needed):
#   bash slurm/setup_deps.sh
#
# The base env already has: torch 2.7.1+cu128, transformers 4.57.0, arc-agi 0.9.8, pillow
# This script adds:          Janus (for Janus-Pro backend)

set -euo pipefail

CONDA_BASE="${CONDA_BASE:-$HOME/miniforge3}"

unset PYTHONPATH
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate base

echo "=== Python: $(which python) — $(python --version) ==="

# DeepSeek Janus-Pro (understanding + autoregressive image generation)
pip install git+https://github.com/deepseek-ai/Janus.git

echo "=== All dependencies installed ==="
python -c "
import arc_agi, PIL, torch, transformers
print(f'arc-agi:      OK')
print(f'torch:        {torch.__version__}')
print(f'transformers: {transformers.__version__}')
try:
    import janus; print('janus:        OK')
except ImportError:
    print('janus: NOT found — check the git install above for errors')
"
