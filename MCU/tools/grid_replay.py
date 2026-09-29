#!/usr/bin/env python3
"""Replay a run's logs.txt through the cell map and count what the map-aware macros
would have had to work with: for every `go_to ... is blocked` note, was a walked cell
nearer the target reachable over the trail (a detour)? For every `dig_down REFUSED:
water`, was a walked cell 8+ blocks from the water reachable (an escape)?

The log has one position per ACTION, not per tick, so the trail is interpolated in
one-block steps between consecutive action positions -- a lower bound on what the
runner's per-tick map holds. Read-only.

    .venv/bin/python tools/grid_replay.py <logs.txt> [...]
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcu_worldmodel.grid import Grid  # noqa: E402

HDR = re.compile(r"^Action (\d+) \| Step (\d+)", re.M)
STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\) pitch=(-?[\d.]+) "
                   r"yaw=(-?[\d.]+)", re.M)
BLOCKED = re.compile(r"go_to \((-?[\d.]+), (-?[\d.]+)\) is blocked at \((-?[\d.]+), (-?[\d.]+)\)")
WATER_REFUSED = re.compile(r"dig_down REFUSED: water")
WATER_SEEN = re.compile(r"the bucket filled -- water_bucket|water was within reach")
DIED = re.compile(r"YOU DIED")


def sections(text: str):
    for part in text.split("=" * 80):
        m = HDR.search(part)
        if not m:
            continue
        s = STATE.search(part)
        pos = ({"x": float(s.group(1)), "y": float(s.group(2)), "z": float(s.group(3)),
                "pitch": float(s.group(4)), "yaw": float(s.group(5))} if s else None)
        yield int(m.group(2)), pos, part


def walk(grid: Grid, step: int, a: dict | None, b: dict) -> None:
    """Interpolate the trail from a to b in <= 1-block steps."""
    if a is None:
        grid.observe(step, b)
        return
    d = math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
    if d > 20:                                  # a death or a portal: not a walk
        grid._last_cell = None
        grid.observe(step, b)
        return
    n = max(1, int(math.ceil(d)))
    for i in range(1, n + 1):
        f = i / n
        grid.observe(step, {"x": a["x"] + (b["x"] - a["x"]) * f,
                            "y": a["y"] + (b["y"] - a["y"]) * f,
                            "z": a["z"] + (b["z"] - a["z"]) * f, "yaw": b.get("yaw", 0.0)})


def replay(path: Path) -> dict:
    grid = Grid()
    prev = None
    out = {"run": path.parent.parent.parent.name, "blocked": 0, "detour": 0,
           "refused": 0, "escape": 0, "cells": 0}
    for step, pos, part in sections(path.read_text(encoding="utf-8", errors="replace")):
        if pos is None:
            continue
        for m in BLOCKED.finditer(part):
            out["blocked"] += 1
            here = {"x": float(m.group(3)), "y": pos["y"], "z": float(m.group(4)), "yaw": pos["yaw"]}
            if grid.detour(here, float(m.group(1)), float(m.group(2))):
                out["detour"] += 1
        if WATER_REFUSED.search(part):
            out["refused"] += 1
            if grid.escape_from_water(pos, 8.0):
                out["escape"] += 1
        if WATER_SEEN.search(part):
            grid.mark_water(step, pos["x"], pos["z"], pos["y"])
        walk(grid, step, prev, pos)
        prev = pos
    out["cells"] = len(grid.walked)
    return out


def main(paths: list[str]) -> None:
    rows = [replay(Path(p)) for p in paths if Path(p).exists()]
    tb = td = tr = te = 0
    for r in rows:
        tb += r["blocked"]; td += r["detour"]; tr += r["refused"]; te += r["escape"]
    print(f"runs {len(rows)}: blocked go_to {tb}, detour available {td} "
          f"({(td / tb if tb else 0):.0%}); water refusals {tr}, escape available {te} "
          f"({(te / tr if tr else 0):.0%})")
    if len(rows) <= 12:
        for r in rows:
            print(f"  {r['run']}: blocked {r['blocked']} detour {r['detour']} | refused "
                  f"{r['refused']} escape {r['escape']} | cells {r['cells']}")


if __name__ == "__main__":
    main(sys.argv[1:])
