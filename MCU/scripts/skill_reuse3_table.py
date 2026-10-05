#!/usr/bin/env python3
"""The endgame skill-probe table (slurm/skill_reuse3.sbatch): the dragon chain's last
eight milestones, each probe started past the search, by what the arm was given.

    skill_reuse3_table.py [--root MCU] [--tag sr3] [--budget 2000] [--json out.json]

Rows are what the arm had: the claim rows are the chain of the agent's own lives (none =
a fresh life, carry = life 2 with life 1's memory, own = a fresh life with only the scripts
those lives WROTE, ownx = another probe's scripts); the fight / macros / recipe rows are
controls that hand the agent harness-written skills or doctrine. Columns are the probes. A
cell is the step at which the probe's last milestone was banked, or `k/n` when the
budget ran out first; replicates are joined with `;`. The tail columns say what the row
did with what it had: calls of a granted macro, calls refused because the macro was not
in the row's set (the model asked for a skill it did not have), deaths, and calls of
scripts the probe wrote. Every number is read from files the lives wrote.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_reuse_table import _json, life  # noqa: E402

#: The claim rows (the chain of the agent's own lives) first, then the controls that hand
#: the agent harness-written skills or doctrine (never part of the reuse claim).
ROWS = ("none", "carry", "carry3", "carry4", "carry5", "carry6", "own", "ownx", "fight", "macros", "recipe")
LABEL = {"none": "the shipped arm, a fresh life (= life 1)",
         "carry": "life 2, carrying life 1's whole memory",
         **{f"carry{n}": f"life {n}, carrying life {n - 1}'s whole memory" for n in range(3, 7)},
         "own": "fresh life + the scripts lives 1 and 2 wrote, nothing else",
         "ownx": "fresh life + another probe's chain's scripts",
         "fight": "CONTROL: + harness face_entity, fight, shoot_bow",
         "macros": "CONTROL: + the harness endgame macros",
         "recipe": "CONTROL: + references/endgame.md (harness prose)"}
TASKS = ("blaze_tail", "enderman_tail", "eye_craft_tail", "end_stone_tail", "dragon_tail")
ARM = re.compile(r"^(?P<tag>.+?)(?:_r(?P<rep>\d+))?_(?P<task>" + "|".join(TASKS)
                 + r")_(?P<row>" + "|".join(ROWS) + r")$")
#: The macros the rows may grant (slurm/skill_reuse3.sbatch GRANT_FIGHT / GRANT_MACROS).
MACROS = ("face_entity", "fight", "shoot_bow", "fight_blaze", "enderman_pit", "explore_nether",
          "throw_eye", "travel_bearing", "fill_end_portal", "enter_end", "mine_end_stone",
          "break_crystal", "attack_dragon")
_ACTION = re.compile(r"^\[ACTION\] ([a-z_]+)\(", re.M)
_REFUSED = re.compile(r"^\[NOTE\] '([a-z_]+)' is (?:withheld in this run|not in this run's procedure set)", re.M)
#: A death the harness named. It names one only when the respawn is a jump of 15+ blocks;
#: the mob probes fight AT the spawn, so most deaths there are not named (pilot 50240421:
#: three kit losses in the none life, no YOU DIED).
_DIED = re.compile(r"^\[NOTE\] YOU DIED", re.M)
#: The deaths that are not named: one [INV] line in which three or more items leave the
#: inventory and none arrives (a craft or a furnace load takes at most two and gives one).
_INV = re.compile(r"^\[INV\] (.+)$", re.M)
#: The sword's use statistic rises on a hit that lands -- and when the sword breaks a
#: block (the game damages the tool and counts a use), which the log writes beside that
#: block's mine_block line. 15 of the blaze carry life's 18 "hits" were block breaks.
_SWORD = re.compile(r"^\[EVENT\] use_item [a-z_]*sword\b")
_BLOCK = re.compile(r"^\[EVENT\] mine_block ")


def entity_hits(text: str) -> int:
    """Sword uses that were hits on a mob: no mine_block line within two lines."""
    lines = text.splitlines()
    n = 0
    for i, line in enumerate(lines):
        if _SWORD.match(line) and not any(
                _BLOCK.match(lines[j]) for j in range(max(0, i - 2), min(len(lines), i + 3))
                if j != i):
            n += 1
    return n
_KILL = re.compile(r"^\[EVENT\] kill_entity ", re.M)


def kit_losses(text: str) -> int:
    n = 0
    for line in _INV.findall(text):
        deltas = re.findall(r"[a-z_]+ ([+-])\d+", line)
        if len(deltas) >= 3 and all(d == "-" for d in deltas):
            n += 1
    return n


def read_log(run: Path) -> dict:
    """What the log says the life did with the macros: calls, refusals, deaths."""
    try:
        text = (run / "episode_001" / "memory" / "logs.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"macro_calls": {}, "refused": {}, "deaths": 0, "hits": 0, "kills": 0}
    calls = Counter(n for n in _ACTION.findall(text) if n in MACROS)
    refused = Counter(n for n in _REFUSED.findall(text) if n in MACROS)
    # line-anchored: the model quotes "[EVENT] kill_entity" and "YOU DIED" in its own plans
    return {"macro_calls": dict(calls), "refused": dict(refused),
            "deaths": max(kit_losses(text), len(_DIED.findall(text))),
            "hits": entity_hits(text), "kills": len(_KILL.findall(text))}


def collect(root: Path, tag: str, tasks: list[str] | None = None) -> dict:
    out = root / "output"
    lives: dict[tuple[str, str], list[dict]] = {}
    for run in sorted(out.iterdir()) if out.is_dir() else []:
        m = ARM.match(run.name)
        if not m or m.group("tag") != tag or (tasks and m.group("task") not in tasks):
            continue
        r = life(run)
        if r is None:
            continue
        rep = _json(run / "episode_001" / "worldmodel_report.json") or {}
        r["finished"] = (root / "logs" / f"{run.name}_result.json").exists()
        r["rep"] = int(m.group("rep") or 1)
        r["granted"] = list(rep.get("granted") or [])
        r["endgame_recipes"] = bool(rep.get("endgame_recipes"))
        r["start_dimension"] = rep.get("start_dimension")
        r.update(read_log(run))
        r["written_calls"] = {n: int(c) for n, c in ((r.get("own") or {}).get("calls") or {}).items()}
        lives.setdefault((m.group("row"), m.group("task")), []).append(r)
    rows = [r for r in ROWS if any(k[0] == r for k in lives)]
    tasks = [t for t in TASKS if any(k[1] == t for k in lives)]
    return {"tag": tag, "rows": rows, "tasks": tasks,
            "lives": {f"{row}/{task}": rs for (row, task), rs in sorted(lives.items())}}


def _cell(rs: list[dict] | None) -> str:
    if not rs:
        return "-"
    parts = []
    for r in sorted(rs, key=lambda r: r["rep"]):
        s = str(r["solved_at"]) if r["done"] else f"{len(r['achieved'])}/{r['total']}"
        if r["deaths"]:
            s += "†" * min(3, r["deaths"])
        if not r["finished"]:
            s += "*"
        parts.append(s)
    return ";".join(parts)


def table(data: dict, budget: int) -> str:
    rows, tasks = data["rows"], data["tasks"]
    head = (["row (what the arm had)"] + tasks
            + ["mean turns", "sword hits landed", "kills", "deaths", "own scripts (reflex fires)",
               "calls of own procedures", "harness macro calls", "refused macro calls"])
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    mean = lambda xs: f"{statistics.mean(xs):.0f}" if xs else "-"  # noqa: E731
    for row in rows:
        rs = [r for t in tasks for r in data["lives"].get(f"{row}/{t}", [])]
        calls = Counter()
        for r in rs:
            calls.update(r["macro_calls"])
        refused = Counter()
        fires = Counter()
        for r in rs:
            refused.update(r["refused"])
            fires.update((r.get("own") or {}).get("reflex_fires") or {})
        cells = [f"{row} ({LABEL[row]})"] + [_cell(data["lives"].get(f"{row}/{t}")) for t in tasks] + [
            mean([r["turns"] for r in rs]),
            str(sum(r["hits"] for r in rs)), str(sum(r["kills"] for r in rs)),
            str(sum(r["deaths"] for r in rs)),
            ", ".join(f"{n} {c}" for n, c in fires.most_common()) or "0",
            str(sum(sum(r["written_calls"].values()) for r in rs)),
            ", ".join(f"{n} {c}" for n, c in calls.most_common()) or "0",
            ", ".join(f"{n} {c}" for n, c in refused.most_common()) or "0"]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"A cell is the step of the probe's last milestone, or banked/total when the "
                 f"{budget}-step budget ran out first; † per death (up to three), * a life still "
                 f"running. Replicates are joined with `;`. Deaths are kit losses read from the log "
                 f"(three or more items gone in one line): the harness names a death only "
                 f"when the respawn is far from where it happened.")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--tag", default="sr3")
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--budget", type=int, default=2000)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()
    data = collect(a.root, a.tag, a.tasks)
    if a.json:
        a.json.write_text(json.dumps(data, indent=1, default=str))
    print(table(data, a.budget))


if __name__ == "__main__":
    main()
