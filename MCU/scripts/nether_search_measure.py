#!/usr/bin/env python3
"""Process measures for the nether_search lives (the --frontier test). Reads each life's
grid.jsonl (walked rows) and worldmodel_report.json; nothing here reaches an agent.

Per life: Nether cells walked, 8x8 tiles walked, how many of the 8 bearings from the start
were walked past 32 blocks, the farthest point, the closest approach to each of the two
mapped fortresses (brick bounding boxes from scripts/fortress_map.py, x/z only), the step
it first came within 48 blocks of one, deaths, and the milestones after netherrack.

  python3 scripts/nether_search_measure.py output/nsf_r1_nether_search_frontier ...
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

START = (-374, -685)
FORTRESSES = {                      # bricks bbox (x0, x1, z0, z1), engine voxel channel
    "NE (-338..-126, -1040..-813)": (-338, -126, -1040, -813),
    "SW (-694..-503, -342..-151)": (-694, -503, -342, -151),
}
NEAR = 48
BEARINGS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def bbox_dist(x, z, b):
    dx = max(b[0] - x, 0, x - b[1])
    dz = max(b[2] - z, 0, z - b[3])
    return math.hypot(dx, dz)


def bearing(dx, dz):
    # N = -z, E = +x
    return BEARINGS[int(((math.degrees(math.atan2(dx, -dz)) + 22.5) % 360) // 45)]


def measure(arm_dir: Path) -> dict:
    ep = arm_dir / "episode_001"
    grid = ep / "memory" / "grid.jsonl"
    rows = [json.loads(l) for l in grid.read_text().splitlines() if l.strip()] if grid.exists() else []
    walked = [r for r in rows if r.get("kind") == "walked"
              and abs(r["cell"][0] - START[0]) < 2000 and abs(r["cell"][2] - START[1]) < 2000]
    out = {"arm": arm_dir.name, "nether_cells": len(walked),
           "tiles": len({(r["cell"][0] // 8, r["cell"][2] // 8) for r in walked})}
    far, reach = 0.0, {}
    for r in walked:
        dx, dz = r["cell"][0] - START[0], r["cell"][2] - START[1]
        d = math.hypot(dx, dz)
        far = max(far, d)
        if d > 8:
            b = bearing(dx, dz)
            reach[b] = max(reach.get(b, 0), round(d))
    out["farthest"] = round(far)
    out["reach"] = {b: reach.get(b, 0) for b in BEARINGS}
    out["bearings_past_32"] = sum(1 for v in reach.values() if v > 32)
    for name, b in FORTRESSES.items():
        best, first = 1e9, None
        for r in walked:
            d = bbox_dist(r["cell"][0], r["cell"][2], b)
            best = min(best, d)
            if first is None and d <= NEAR:
                first = r["step"]
        out[f"closest {name}"] = round(best) if walked else None
        out[f"first<= {NEAR} {name}"] = first
    out["coverage_rows"] = sum(1 for r in rows if r.get("kind") == "coverage")
    rep = ep / "worldmodel_report.json"
    if rep.exists():
        d = json.loads(rep.read_text())
        ach = (d.get("milestones") or {}).get("achieved") or {}
        given = set((d.get("milestones") or {}).get("given") or [])
        out["new_milestones"] = {k: v for k, v in ach.items() if k not in given}
        out["steps"] = d.get("steps")
    log = ep / "memory" / "logs.txt"
    if log.exists():
        t = log.read_text(errors="replace")
        out["named_deaths"] = sum(1 for l in t.splitlines() if l.startswith("[NOTE] YOU DIED"))
    return out


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(json.dumps(measure(Path(a))))
