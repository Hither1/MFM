#!/usr/bin/env python3
"""Phase metrics for one or more arms, read from the run artefacts alone.

    .venv/bin/python scripts/phase_metrics.py kd21z_wm_high kd21z_lb_high
    .venv/bin/python scripts/phase_metrics.py --glob 'kd21*'

One row per arm. Everything comes from files a finished OR running arm already has,
so a wave can be read mid-flight instead of waited for:

  logs/<arm>_green.log        -> milestone_tracking.json path (steps per milestone)
  logs/<arm>_result.json      -> score, when landed
  output/<arm>/episode_001/memory/{logs.txt, maps/visited.csv, events/events.jsonl}
  output/<arm>/episode_001/worldmodel_report.json -> turns, calls

Columns: score, n milestones, step of stone pickaxe / furnace / first torch craft /
first descent below y20 / first iron ore / iron ingot / iron pickaxe / diamond, search
ticks (stone pickaxe -> first ore, or -> now), share of the search window spent at
y<=16, deaths, damage notes, discard_stack calls, free-slot reading on the last turn,
act turns, codex calls. `-` means not (yet) reached.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _milestones(arm: str) -> dict[str, int]:
    g = os.path.join(ROOT, "logs", f"{arm}_green.log")
    if not os.path.exists(g):
        return {}
    m = re.search(r"Milestone data saved to: (\S+)", open(g, errors="ignore").read())
    if not m or not os.path.exists(m.group(1)):
        return {}
    d = json.load(open(m.group(1)))
    return {x["identity"]: int(x["step"]) for x in d.get("milestones", [])}


def _milestones_live(arm: str) -> dict[str, int]:
    """Before the green log has a tracking file: the harness's own events channel."""
    p = os.path.join(ROOT, "output", arm, "episode_001", "memory", "events", "events.jsonl")
    out: dict[str, int] = {}
    if not os.path.exists(p):
        return out
    for line in open(p, errors="ignore"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") == "milestone" and d.get("identity") not in out:
            out[d["identity"]] = int(d["step"])
    return out


def _milestones_log(arm: str) -> dict[str, int]:
    """Logbook/direct arms have no events channel: read the [EVENT] MILESTONE lines
    from logs.txt, dated by the action block they were logged under."""
    p = os.path.join(ROOT, "output", arm, "episode_001", "memory", "logs.txt")
    out: dict[str, int] = {}
    if not os.path.exists(p):
        return out
    step = 0
    for line in open(p, errors="ignore"):
        m = re.search(r"Action \d+ \| Step (\d+)", line)
        if m:
            step = int(m.group(1))
            continue
        m = re.search(r"MILESTONE (\w+) verified", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = step
    return out


def _events(arm: str) -> list[dict]:
    p = os.path.join(ROOT, "output", arm, "episode_001", "memory", "events", "events.jsonl")
    out = []
    if os.path.exists(p):
        for line in open(p, errors="ignore"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _visited(arm: str) -> list[tuple[int, float]]:
    """(step, y) samples: every step from visited.csv where the harness keeps it (the
    worldmodel arm), else one per logged action block from logs.txt (logbook/direct
    arms get no maps/ channel), so the same columns read across the ladder."""
    p = os.path.join(ROOT, "output", arm, "episode_001", "memory", "maps", "visited.csv")
    out = []
    if os.path.exists(p):
        with open(p, errors="ignore") as f:
            for row in csv.DictReader(f):
                try:
                    out.append((int(row["step"]), float(row["y"])))
                except (KeyError, ValueError):
                    pass
        if out:
            return out
    lp = os.path.join(ROOT, "output", arm, "episode_001", "memory", "logs.txt")
    if os.path.exists(lp):
        step = None
        for line in open(lp, errors="ignore"):
            m = re.search(r"Action \d+ \| Step (\d+)", line)
            if m:
                step = int(m.group(1))
                continue
            m = re.search(r"pos=\(-?[\d.]+, (-?[\d.]+), -?[\d.]+\)", line)
            if m and step is not None:
                out.append((step, float(m.group(1))))
    return out


def row(arm: str) -> dict:
    ms = _milestones(arm) or _milestones_live(arm) or _milestones_log(arm)
    ev = _events(arm)
    vis = _visited(arm)
    now = vis[-1][0] if vis else 0
    rf = os.path.join(ROOT, "logs", f"{arm}_result.json")
    score = None
    if os.path.exists(rf):
        try:
            score = json.load(open(rf))["results"][0]["total_score"]
        except Exception:
            score = None
    first = {}
    for d in ev:
        key = (d.get("event"), d.get("item"))
        if key not in first:
            first[key] = int(d["step"])
    torch = first.get(("craft_item", "torch"))
    stone = ms.get("stone_pickaxe") or ms.get("craft_stone_pickaxe")
    ore = ms.get("mine_iron_ore")
    descent = next((s for s, y in vis if y <= 20.0), None)
    search_end = ore or now
    search = (search_end - stone) if stone else None
    deep_share = None
    if stone:
        win = [(s, y) for s, y in vis if stone <= s <= search_end]
        if win:
            deep_share = sum(1 for _, y in win if y <= 16.0) / len(win)
    lp = os.path.join(ROOT, "output", arm, "episode_001", "memory", "logs.txt")
    deaths = dmg = discards = 0
    free_last = None
    if os.path.exists(lp):
        txt = open(lp, errors="ignore").read()
        deaths = txt.count("YOU DIED")
        dmg = len(re.findall(r"\[NOTE\] (?:took \d+ damage|lost \d+ health)", txt))
        discards = txt.count('"discard_stack"') + txt.count("discard_stack(")
    turns = calls = None
    rp = os.path.join(ROOT, "output", arm, "episode_001", "worldmodel_report.json")
    if os.path.exists(rp):
        try:
            rep = json.load(open(rp))
            turns = (rep.get("turns") or {}).get("act")
            calls = (rep.get("codex") or {}).get("calls")
        except Exception:
            pass
    pdir = os.path.join(ROOT, "output", arm, "episode_001", "codex_turns")
    prompts = sorted(glob.glob(os.path.join(pdir, "turn_*.prompt.txt")))
    if prompts:
        m = re.search(r"Inventory \((\S+) slots free\)", open(prompts[-1], errors="ignore").read())
        free_last = m.group(1) if m else None
    return {
        "arm": arm, "score": score, "n": len(ms), "now": now,
        "stone": stone, "furnace": ms.get("furnace"), "torch": torch,
        "y<=20": descent, "ore": ore, "ingot": ms.get("iron_ingot"),
        "ipick": ms.get("iron_pickaxe"), "diamond": ms.get("diamond"),
        "search": search, "deep%": None if deep_share is None else round(100 * deep_share),
        "deaths": deaths, "dmg": dmg, "discard": discards, "free": free_last,
        "turns": turns, "calls": calls,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="*")
    ap.add_argument("--glob", default=None)
    a = ap.parse_args()
    arms = list(a.arms)
    if a.glob:
        arms += sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "output", a.glob)))
    if not arms:
        ap.error("name arms or pass --glob")
    cols = ["arm", "score", "n", "now", "stone", "furnace", "torch", "y<=20", "ore", "ingot",
            "ipick", "diamond", "search", "deep%", "deaths", "dmg", "discard", "free",
            "turns", "calls"]
    rows = [row(x) for x in arms]
    widths = {c: max(len(c), *(len(str(r[c]) if r[c] is not None else "-") for r in rows))
              for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join((str(r[c]) if r[c] is not None else "-").ljust(widths[c]) for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
