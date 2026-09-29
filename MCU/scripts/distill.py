#!/usr/bin/env python3
"""CLI for mcu_worldmodel.distill: the distiller pass between two lives.

    PYTHONPATH=<MFM root>:. CODEX_BIN=codex .venv/bin/python scripts/distill.py \\
        --out output/og23_distill --codex-home $MCU_CODEX_ROOT/og23_distill \\
        --seed-memory <life>/episode_001/memory [--seed-memory ...] --model gpt-5.6-sol --reasoning-effort xhigh
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcu_worldmodel.distill import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
