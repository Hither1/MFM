#!/usr/bin/env bash
# Wait for ofN_mfm's run-arm.sh (logs/ofN_mfm_launch.pid) to exit -- the 8h wall watchdog stops it --
# then launch ofNr_mfm, the memory-reuse life (launch_ofr.sh). Detached by the caller; log in
# MCU/logs/ofNr_mfm_chain.log.
set -u
N="${1:?usage: chain_ofr.sh <1|2|3>}"
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
PID=$(cat "logs/of${N}_mfm_launch.pid")
echo "$(date '+%F %T') waiting for of${N}_mfm (run-arm pid $PID) to exit"
while kill -0 "$PID" 2>/dev/null; do sleep 60; done
echo "$(date '+%F %T') of${N}_mfm run-arm exited; waiting 90 s for the tree to settle"
sleep 90
echo "$(date '+%F %T') of${N}_mfm milestones: $(grep -c '\[milestone\]' logs/of${N}_mfm_purple.log) last: $(grep '\[milestone\]' logs/of${N}_mfm_purple.log | tail -1 | sed 's/.*\[milestone\] //')"
echo "$(date '+%F %T') launching of${N}r_mfm"
bash /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/tasks/mfm-three-layer.spatial-grid/scripts/launch_ofr.sh "$N"
echo "$(date '+%F %T') launch_ofr.sh $N returned $?"
