#!/usr/bin/env bash
# Settle the voxel channel before a nether-portal wave.
#
#   sbatch slurm/portal_probe.sbatch
#
# The whole case study is scored from `info["voxels"]`, and everything portal.py assumes
# about that channel -- offsets relative to the player, air omitted, exclusive upper
# bounds, full block ids -- was read out of the engine jar, not out of a run. If any of
# it is wrong nothing raises: every frame scores 0/10 and a wave of arms looks like it
# failed at geometry when it failed at plumbing.
#
# Minutes, not hours: no codex, no A2A servers, no model calls. One MinecraftSim, a
# handful of /setblock, a portal read back through the scorer. Environment is
# aba_probe.sbatch's, which is arm.sbatch's minus the agents.
#SBATCH -J mcu-portal-probe
#SBATCH -p sapphire
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 0:30:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

set -euo pipefail
ROOT=${MCU_ROOT:-/n/holylfs06/LABS/sham_lab/Users/$USER/MFM/MCU}
cd "$ROOT"
mkdir -p slurm/logs output

echo "=== job $SLURM_JOB_ID on $(hostname -s) | $(date -Is) ==="
echo "root=$ROOT  head=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"

export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export JAVA_HOME=${JAVA_HOME:-/usr}
export MCU_SKIP_ENV_SH=1
DISPLAY_NUM=$(( (SLURM_JOB_ID % 55000) + 200 ))
echo "display=:$DISPLAY_NUM minestudio_dir=$MINESTUDIO_DIR"

# The engine interpreter the runners use (worldmodel.sbatch, solo.sbatch), NOT
# `.venv/bin/python`. In this checkout `.venv` is a symlink to another tree whose
# uv-managed interpreter is gone, so `.venv/bin/python` is a dangling link and
# xvfb-run exits in nine seconds with "No such file or directory" -- which is also
# what aba_probe.sbatch would do today. Overridable for a checkout that has its own.
PY=${MCU_PYTHON:-$HOME/miniforge3/envs/minestudio/bin/python}
echo "python=$PY"

xvfb-run --server-num="$DISPLAY_NUM" -s "-screen 0 1024x768x24" \
    "$PY" -u -m mcu_worldmodel.portal_voxel_probe \
    --out "output/portal_voxel_probe_${SLURM_JOB_ID}.json"
rc=$?
echo "probe exit=$rc (0 = the voxel channel reads as portal.py assumes)  finished=$(date -Is)"
exit $rc
