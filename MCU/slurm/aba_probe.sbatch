#!/usr/bin/env bash
# Settle one question before an A-B-A wave: does filling a bucket move `use_item.bucket`?
#
#   sbatch slurm/aba_probe.sbatch
#
# Minutes, not hours: no codex, no A2A servers, no model calls. One MinecraftSim, one
# /fill of water, a few right-clicks. The env setup below is arm.sbatch's, minus
# everything to do with the agents -- same engine, same node-local MINESTUDIO_DIR, same
# job-id display number so a probe cannot race an arm onto one X server.
#
# `-c 4 / 8G / 30 min` rather than arm.sbatch's 12 / 48G / 2.5 days: this steps the
# simulator a few dozen times and exits.
#SBATCH -J mcu-aba-probe
#SBATCH -p sapphire
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 0:30:00
#SBATCH -o slurm/logs/%x-%j.out
#SBATCH -e slurm/logs/%x-%j.err

set -euo pipefail
# Defaults to THIS checkout, not the campaign tree: the ABA task configs and the loaders
# under test live here.
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

xvfb-run --server-num="$DISPLAY_NUM" -s "-screen 0 1024x768x24" \
    .venv/bin/python -u -m mcu_worldmodel.aba_bucket_probe \
    --out "output/aba_bucket_probe_${SLURM_JOB_ID}.json"
rc=$?
echo "probe exit=$rc (0 = use_item.bucket fired)  finished=$(date -Is)"
exit $rc
