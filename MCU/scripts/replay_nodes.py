#!/usr/bin/env python3
"""Replay a landed worldmodel arm's artefacts through the harness-node generators.

    .venv/bin/python scripts/replay_nodes.py kd20z_wm_high [--at STEP]

Feeds the run's own channels -- positioned stat events (events.jsonl + visited.csv),
the death/damage notes and the mining macros' completion notes (logs.txt) -- through
the same agent methods the live harness calls (sites.py), and prints the graph nodes
and the act-prompt block the run WOULD have seen at `--at` (default: the end). This is
how a change to sites.py is judged on old trajectories before it costs a wave.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mcu_worldmodel import sites  # noqa: E402
from mcu_worldmodel.agent import WorldModelAgent  # noqa: E402
from mcu_worldmodel.milestones import MilestoneLedger  # noqa: E402

_NOTE_HIT = re.compile(r"\[NOTE\] took (\d+) damage -- health \d+/20 at \((-?\d+), (-?\d+), (-?\d+)\)")
_NOTE_DEATH = re.compile(r"\[NOTE\] YOU DIED at \((-?\d+), (-?\d+), (-?\d+)\)")
_NOTE_MACRO = re.compile(
    r"\[NOTE\] (strip_mine|mine_forward|stair_down|dig_down): broke (\d+) blocks, "
    r"(?:advanced ([\d.]+) blocks|descended ([\d.]+)) in (\d+) ticks")
_ORE_FLAG = re.compile(r"\[NOTE\] mining stopped: iron-ore-like speckles")


def load_visited(mem: str) -> tuple[list[int], list[dict[str, float]]]:
    steps, poss = [], []
    p = os.path.join(mem, "maps", "visited.csv")
    with open(p, errors="ignore") as f:
        for row in csv.DictReader(f):
            try:
                steps.append(int(row["step"]))
                poss.append({"x": float(row["x"]), "y": float(row["y"]),
                             "z": float(row["z"]), "pitch": float(row["pitch"]),
                             "yaw": float(row["yaw"])})
            except (KeyError, ValueError):
                pass
    return steps, poss


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--at", type=int, default=None)
    a = ap.parse_args()
    mem = os.path.join(ROOT, "output", a.arm, "episode_001", "memory")
    steps, poss = load_visited(mem)

    def pos_at(step: int) -> dict[str, float]:
        i = bisect.bisect_right(steps, step) - 1
        return poss[max(0, i)]

    # Timeline: (step, kind, payload)
    tl: list[tuple[int, str, object]] = []
    for line in open(os.path.join(mem, "events", "events.jsonl"), errors="ignore"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") != "stat":
            continue
        item = str(d.get("item", ""))
        if (d.get("event") == "use_item" and item in sites.SITE_ITEMS) or (
                d.get("event") == "mine_block" and (item in sites.SITE_ITEMS or item.endswith("_ore"))):
            tl.append((int(d["step"]), "stat", {"event": d["event"], "item": item,
                                               "delta": float(d.get("delta", 1))}))
    step = 0
    for line in open(os.path.join(mem, "logs.txt"), errors="ignore"):
        m = re.search(r"Action \d+ \| Step (\d+)", line)
        if m:
            step = int(m.group(1))
            continue
        if _ORE_FLAG.search(line):
            tl.append((step, "flag", None))
        m = _NOTE_HIT.search(line)
        if m:
            tl.append((step, "hit", (float(m.group(1)), {"x": float(m.group(2)),
                                                          "y": float(m.group(3)),
                                                          "z": float(m.group(4)), "yaw": 0.0})))
            continue
        m = _NOTE_DEATH.search(line)
        if m:
            tl.append((step, "death", {"x": float(m.group(1)), "y": float(m.group(2)),
                                       "z": float(m.group(3)), "yaw": 0.0}))
            continue
        m = _NOTE_MACRO.search(line)
        if m:
            tl.append((step, "macro", (m.group(1), int(m.group(2)),
                                       float(m.group(3) or m.group(4) or 0.0), int(m.group(5)))))
    tl.sort(key=lambda t: t[0])
    end = a.at if a.at is not None else (steps[-1] if steps else 0)

    with tempfile.TemporaryDirectory() as tmp:
        agent = WorldModelAgent(workspace=os.path.join(tmp, "ws"), task_text="replay",
                                ledger=MilestoneLedger([], "t"), induction_every=0)
        for s, kind, payload in tl:
            if s > end:
                break
            agent.step = s
            if kind == "stat":
                agent._cur_pos = pos_at(s)
                agent._harness_events([payload], agent._cur_pos, s)
            elif kind == "flag":
                agent.cursor_stats["ore_flagged"] = agent.cursor_stats.get("ore_flagged", 0) + 1
            elif kind == "hit":
                dmg, p = payload
                agent._cur_pos = p
                agent._add_hit(p, s, dmg)
            elif kind == "death":
                agent.graph.add_or_update(
                    id=f"hazard_death_{s}", kind="location",
                    statement=sites.death_statement(payload, s), confidence=1.0,
                    status="confirmed", step=s)
            elif kind == "macro":
                label, broken, adv, used = payload
                agent._cur_pos = pos_at(s)
                agent._record_coverage(label, None, broken, adv, used)
            if agent._cur_pos:
                agent.discipline.note_visits(agent._cur_pos, s)
        here = pos_at(end)
        print(f"{a.arm} at step {end}: {len(agent.graph.nodes)} harness nodes "
              f"({sum(1 for n in agent.graph.nodes if n.startswith('site_'))} sites, "
              f"{sum(1 for n in agent.graph.nodes if n.startswith('hazard_'))} hazards)\n")
        print("Harness facts block as the act prompt would show it here "
              f"({here['x']:.0f}, {here['y']:.0f}, {here['z']:.0f}):")
        print(sites.render_block(agent.graph, here, end, agent.discipline.visits) or "(empty)")
        print("\nAll nodes:")
        for n in sorted(agent.graph.nodes.values(), key=lambda n: n.created_step):
            print(f"- [{n.id}] ({n.kind}, {n.status}, {n.confidence:.2f}) {n.statement[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
