#!/usr/bin/env bash
# og23: og22's setting (thin+atoms+own+own-reflexes, no harness reflexes, skills, gpt-5.6-sol xhigh)
#       + memory v2 (frames in [OBSERVED], RECALL bearings, then-now, working.md, skill examples)
#       + the distiller pass output (--seed-mine), seeded with og19's clean lives + og15 + og18.
# og24: og23 + --minimal (VISTA's short contract).
#   bash launch_og23_og24.sh distill   # first: the distiller pass (background, ~40 min)
#   bash launch_og23_og24.sh og23      # after distill_report.json shows guide_lines > 0
#   bash launch_og23_og24.sh og24
set -euo pipefail
cd /datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU
export MCU_CODEX_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/codex-homes
export CODEX_BIN=$HOME/ccr/bin/codex
M=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output
G=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output
OLD=/datapool/data3/storage/ruihan/data_share/jh/Collab/MCU-AgentBeats/output
GRID="og3_mfm og4_mfm og12_mfm og13_mfm og14_mfm og15_mfm"
EXTRA="$M/og8_mfm/episode_001/memory $M/og9_mfm/episode_001/memory $M/og16_mfm/episode_001/memory $M/og17_mfm/episode_001/memory $M/og18_mfm/episode_001/memory"
FLAGS="--expect --frames --retrieval --frame-size 320x180 --model gpt-5.6-sol --reasoning-effort xhigh --thin --atoms --own --own-reflexes --no-harness-reflexes --skills"
if [ "${1:-}" = "distill" ]; then
  SEEDS=""
  for a in hd12z_wm_high hd32z_wm_high hd39z_wm_high hd43z_wm_high hd41z_wm_high kd35z_lb_high dm16_wm_high dm17_wm_high kd14x_wm_high kd31z_lb_high kd6_wm_high kdc3z_logbook_high; do SEEDS="$SEEDS $OLD/$a/episode_001/memory"; done
  for a in $GRID; do SEEDS="$SEEDS $G/$a/episode_001/memory"; done
  SEEDS="$SEEDS $EXTRA"
  mkdir -p logs
  MFM_ROOT=/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid MINUTES=45 \
    setsid nohup bash scripts/distill.sh og23_distill output/og23_distill $SEEDS > logs/og23_distill.log 2>&1 < /dev/null &
  echo $! > logs/og23_distill.pid; echo "distiller pid $(cat logs/og23_distill.pid); logs/og23_distill.log"
fi
if [ "${1:-}" = "og23" ]; then
  [ -s output/og23_distill/memory/mine/GUIDE.md ] || { echo "no GUIDE.md from the distiller yet" >&2; exit 1; }
  ARM=og23_mfm GP=9127 PP=9137 STEPS=60000 SESSION_TURNS=0 COMPACT=1 WALL=10h \
  GRID_SEEDS="$GRID" EXTRA_SEEDS="$EXTRA" \
  WM_EXTRA="$FLAGS --seed-mine $G/og23_distill/memory/mine" bash scripts/launch-og.sh
fi
if [ "${1:-}" = "og24" ]; then
  [ -s output/og23_distill/memory/mine/GUIDE.md ] || { echo "no GUIDE.md from the distiller yet" >&2; exit 1; }
  ARM=og24_mfm GP=9128 PP=9138 STEPS=60000 SESSION_TURNS=0 COMPACT=1 WALL=10h \
  GRID_SEEDS="$GRID" EXTRA_SEEDS="$EXTRA" \
  WM_EXTRA="$FLAGS --minimal --seed-mine $G/og23_distill/memory/mine" bash scripts/launch-og.sh
fi
