#!/usr/bin/env bash
# Run a stage/probe module from this worktree with the engine environment loaded.
#   bash probes/run_stage.sh probes/probe_end.py            (a script)
#   bash probes/run_stage.sh -m mcu_worldmodel.stages.s10_end (a module)
set -u
cd "$(dirname "$0")/.."
source ./env.sh
export PYTHONPATH="$PWD:${MFM_ROOT:-$PWD/..}"   # the mfm package lives in the MFM checkout above
export MCU_STAGE_OUT="${MCU_STAGE_OUT:-$PWD/logs/stages}"
V=/datapool/data3/storage/ruihan/data_share/jh/Collab/MCU-AgentBeats/.venv/bin/python
exec xvfb-run -a "$V" "$@"
