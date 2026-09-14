#!/usr/bin/env bash
# slurm/arm.sbatch plus the collab launcher's WALL cap (launch-og.sh): at WALL the arm's
# tree is stopped by pid (scripts/stop_arm.py), whatever step it is on; the workspace log,
# audit and milestones up to then stand, as for every gen-4 dragon arm. A file of its own
# so MCU_ROOT's arm.sbatch is never edited while jobs execute it.
#   sbatch [-t ...] arm_wall.sbatch <agent> <arm> <task> <steps> <wall> [run-arm.sh args...]
#SBATCH -J mcu-arm-wall
#SBATCH -p sapphire
#SBATCH -c 12
#SBATCH --mem=48G
#SBATCH -t 1-06:00:00
set -uo pipefail
AGENT=${1:?agent}; ARM=${2:?arm}; TASK=${3:?task}; STEPS=${4:?steps}; WALL=${5:?wall}
shift 5
: "${MCU_ROOT:?MCU_ROOT is the gen-4 checkout}"
cd "$MCU_ROOT"
echo "=== wall cap $WALL for $ARM ($AGENT, $TASK, $STEPS steps) ==="
( sleep "$WALL"; echo "wall $WALL reached at $(date -Is): stopping $ARM"; \
  "$MCU_ROOT/.venv/bin/python" "$MCU_ROOT/scripts/stop_arm.py" --go "$ARM" ) &
WD=$!
bash "$MCU_ROOT/slurm/arm.sbatch" "$AGENT" "$ARM" "$TASK" "$STEPS" "$@"
RC=$?
kill "$WD" 2>/dev/null
echo "arm.sbatch exited $RC at $(date -Is)"
