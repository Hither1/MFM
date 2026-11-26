#!/usr/bin/env python3
"""Where a nether_search life's 20k steps went (instrument; nothing reaches an agent).

Reads memory/index.jsonl + episodes/<id>/{action.json,outcome.json,state/state.json}. Each
row is one executed plan entry covering steps first..last; its start pose is its state.json,
its end pose the next row's. Every row's steps go to ONE category, first match wins:

  overworld   the row starts outside the Nether box (a portal trip, the pre-teleport frame)
  death       a YOU DIED note, or the next row starts 15+ blocks away without a portal
  dig         a block was mined (mine_block event)
  build       a block was placed (use_item of a placeable block)
  hurt        health fell during the row and nothing above
  walk        moved >= 1 block (x, z); split by whether sneak was held
  look        only camera / hotbar / sneak keys
  blocked     forward/jump/sprint held and moved < 1 block
  idle        anything else (noop, use, attack with nothing broken)

Also: the farthest distance from the start reached by each 2.5k steps, and progress
efficiency = steps per block of NEW farthest distance.

  python3 scripts/nether_step_budget.py output/<arm> ...   (--json for one line per life)
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

START = (-374.0, -685.0)
PLACEABLE = ("cobblestone", "netherrack", "obsidian", "basalt", "blackstone", "planks",
             "crafting_table", "furnace", "torch", "dirt", "stone", "soul_sand", "gravel")
MOVE_KEYS = {"forward", "back", "left", "right", "jump", "sprint"}
LOOK_KEYS = {"camera", "sneak"}


def nether(x, z):
    return abs(x - START[0]) < 1200 and abs(z - START[1]) < 1200


def keys_of(entry):
    a = (entry or {}).get("action")
    if isinstance(a, dict):
        return {k for k, v in a.items() if v not in (0, None, [0, 0], [0.0, 0.0])}
    return set()


def load(arm: Path):
    mem = arm / "episode_001" / "memory"
    rows = []
    for line in (mem / "index.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("kind") != "episode":
            continue
        ep = mem / r["path"]
        try:
            st = json.loads((ep / "state" / "state.json").read_text())
            out = json.loads((ep / "outcome.json").read_text())
            act = json.loads((ep / "action.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rows.append({"first": int(r["first_step"]), "last": int(r["last_step"]),
                     "pos": st.get("pos") or {}, "hp": (st.get("vitals") or {}).get("health"),
                     "events": out.get("events") or [], "notes": out.get("notes") or [],
                     "keys": keys_of(act.get("entry")), "kind": r.get("action_kind") or "",
                     "end": (r.get("x"), r.get("z"))})
    rows.sort(key=lambda r: r["first"])
    return rows


def classify(r, nxt):
    p = r["pos"]
    if p.get("x") is None:
        return "idle", 0.0
    x, z = float(p["x"]), float(p["z"])
    if not nether(x, z):
        return "overworld", 0.0
    q = nxt["pos"] if nxt else None
    ex, ez = (float(q["x"]), float(q["z"])) if q and q.get("x") is not None else (
        r["end"] if r["end"][0] is not None else (x, z))
    d = math.hypot(ex - x, ez - z)
    if not nether(ex, ez):
        return "overworld", 0.0          # the row that ends in a portal trip
    if any("YOU DIED" in n for n in r["notes"]) or (d > 15 and nether(ex, ez)):
        return "death", 0.0
    ev = " ".join(r["events"])
    if "mine_block" in ev:
        return "dig", d
    if any(f"use_item {b}" in ev for b in PLACEABLE):
        return "build", d
    hp1 = nxt["hp"] if nxt else None
    if r["hp"] is not None and hp1 is not None and hp1 < r["hp"]:
        return "hurt", d
    if d >= 1.0:
        return ("walk (sneak)" if "sneak" in r["keys"] else "walk"), d
    if r["keys"] and r["keys"] <= LOOK_KEYS | {k for k in r["keys"] if k.startswith("hotbar")}:
        return "look", d
    if r["keys"] & MOVE_KEYS:
        return "blocked", d
    return "idle", d


def measure(arm: Path):
    rows = load(arm)
    steps, dist = Counter(), defaultdict(float)
    far, far_by, prog = 0.0, {}, []
    for i, r in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        n = max(1, r["last"] - r["first"] + 1)
        cat, d = classify(r, nxt)
        steps[cat] += n
        dist[cat] += d
        p = r["pos"]
        if p.get("x") is not None and nether(float(p["x"]), float(p["z"])):
            f = math.hypot(float(p["x"]) - START[0], float(p["z"]) - START[1])
            if f > far:
                prog.append((r["first"], round(f)))
                far = f
        for cut in range(2500, 22501, 2500):
            if r["first"] <= cut:
                far_by[cut] = round(far)
    total = sum(steps.values())
    walk_steps = steps["walk"] + steps["walk (sneak)"]
    return {"arm": arm.name, "steps": total,
            "share": {k: round(v / total, 3) for k, v in steps.most_common()},
            "blocks_moved": {k: round(v) for k, v in dist.items() if v >= 1},
            "walk_speed_blocks_per_step": {
                "walk": round(dist["walk"] / steps["walk"], 3) if steps["walk"] else None,
                "walk (sneak)": round(dist["walk (sneak)"] / steps["walk (sneak)"], 3)
                if steps["walk (sneak)"] else None},
            "sneak_share_of_walking": round(steps["walk (sneak)"] / walk_steps, 2) if walk_steps else None,
            "farthest_by_step": far_by, "farthest": round(far),
            "steps_per_new_block": round(total / far, 1) if far else None}


def show(m):
    print(f"== {m['arm']}  ({m['steps']} steps, farthest {m['farthest']}, "
          f"{m['steps_per_new_block']} steps per block of new distance)")
    print("   share of steps: " + ", ".join(f"{k} {100 * v:.0f}%" for k, v in m["share"].items()))
    print(f"   walking speed (blocks/step): {m['walk_speed_blocks_per_step']}; sneaking = "
          f"{m['sneak_share_of_walking']} of walking steps")
    print(f"   blocks moved by category: {m['blocks_moved']}")
    print(f"   farthest by step: {m['farthest_by_step']}")


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    for a in [x for x in sys.argv[1:] if x != "--json"]:
        m = measure(Path(a))
        print(json.dumps(m)) if as_json else show(m)
