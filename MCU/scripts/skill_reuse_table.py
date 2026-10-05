#!/usr/bin/env python3
"""The skill-reuse table: how fast a new task is solved from the memory of a diamond life
as that memory stood at each checkpoint (slurm/skill_reuse.sbatch).

    skill_reuse_table.py [--root MCU] [--tag sr] [--budget 6000] [--json out.json]

Rows are checkpoints of the source life (0 = no memory carried); columns are the probe
tasks. A cell is the step at which the task's last milestone was banked, or `k/n` when
the budget ran out first. Every number is read from files the lives wrote:
`output/<arm>/episode_001/worldmodel_report.json` (the ledger's milestone steps, the
turn count), `codex_turns/*.events.jsonl` (model calls, refused turns, cost), and the
cut's `.cut.json` and `mine/` for what the carried memory held.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ARM = re.compile(r"^(?P<tag>.+?)(?:_r(?P<rep>\d+))?_(?P<task>cook_meat|coal_torches|iron_shield)"
                 r"_t(?P<t>\d{5})$")
OPENING = "cobblestone"          # the last milestone the three tasks share
#: The examples shipped under skills/*/scripts, which a life copies into mine/ on its
#: first turn: not counted as written by the model.
SHIPPED = {"aim_speckles", "shaft_down", "stair_step", "strip_segment", "torch_wall",
           "fell", "hit", "lava_ahead", "starving"}


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def calls(turns_dir: Path) -> dict:
    """Model calls, refused turns and cost of a life, from the CLI's own event files."""
    out = {"turn_files": 0, "model_calls": 0, "errors": 0, "refused": 0, "cost_usd": 0.0}
    for p in sorted(turns_dir.glob("turn_*.events.jsonl")):
        out["turn_files"] += 1
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "rate_limit_event":
                if (e.get("rate_limit_info") or {}).get("status") not in (None, "allowed",
                                                                         "allowed_warning"):
                    out["refused"] += 1
            if e.get("type") != "result":
                continue
            out["model_calls"] += int(e.get("num_turns") or 0)
            out["cost_usd"] += float(e.get("total_cost_usd") or 0.0)
            if e.get("is_error"):
                out["errors"] += 1
    out["cost_usd"] = round(out["cost_usd"], 2)
    return out


def life(run: Path) -> dict | None:
    rep = _json(run / "episode_001" / "worldmodel_report.json")
    if rep is None:
        return None
    ms = rep.get("milestones") or {}
    achieved = {k: int(v) for k, v in (ms.get("achieved") or {}).items()}
    order = list(ms.get("order") or [])
    total = int(ms.get("total_milestones") or len(order))
    done = len(achieved) >= total > 0
    return {
        "arm": run.name, "steps": int(rep.get("steps") or 0),
        "turns": int((rep.get("turns") or {}).get("act") or 0),
        "turns_failed": int((rep.get("turns") or {}).get("act_failed") or 0),
        "achieved": achieved, "order": order, "total": total, "done": done,
        "solved_at": max(achieved.values()) if done else None,
        "opening_at": achieved.get(OPENING),
        "carried_world": rep.get("carried_world"),
        "own": rep.get("own"),
        **calls(run / "episode_001" / "codex_turns"),
    }


def memory_row(root: Path, tag: str, t: int, source: dict | None) -> dict:
    """What the carried memory held at checkpoint t."""
    if t == 0:
        return {"t": 0, "episodes": 0, "milestones": 0, "written": [], "guide_bytes": 0,
                "notes_bytes": 0}
    cut = root / "output" / f"{tag}_mem" / f"t{t:05d}"
    info = _json(cut / ".cut.json") or {}
    mine = cut / "mine"
    written = sorted(p.stem for d in ("procedures", "reflexes") for p in (mine / d).glob("*.py")
                     if p.stem not in SHIPPED) if mine.is_dir() else []
    size = lambda n: (mine / n).stat().st_size if (mine / n).exists() else 0  # noqa: E731
    reached = sum(1 for s in (source or {}).get("achieved", {}).values() if s <= t)
    return {"t": t, "episodes": (info.get("episodes") or {}).get("kept"),
            "milestones": reached, "written": written,
            "guide_bytes": size("GUIDE.md"), "notes_bytes": size("notes.md")}


def collect(root: Path, tag: str) -> dict:
    out = root / "output"
    lives: dict[tuple[int, str], list[dict]] = {}
    for run in sorted(out.iterdir()) if out.is_dir() else []:
        m = ARM.match(run.name)
        if not m or m.group("tag") != tag:
            continue
        row = life(run)
        if row is None:
            continue
        row["finished"] = (root / "logs" / f"{run.name}_result.json").exists()
        row["rep"] = int(m.group("rep") or 1)
        lives.setdefault((int(m.group("t")), m.group("task")), []).append(row)
    source = life(out / f"{tag}_src_diamond")
    points = sorted({t for t, _ in lives})
    tasks = [t for t in ("cook_meat", "coal_torches", "iron_shield")
             if any(k[1] == t for k in lives)]
    return {"tag": tag, "source": source, "points": points, "tasks": tasks,
            "memory": [memory_row(root, tag, t, source) for t in points],
            "lives": {f"{t}/{task}": rows for (t, task), rows in sorted(lives.items())}}


def _cell(rows: list[dict] | None, budget: int) -> str:
    if not rows:
        return "--"
    parts = []
    for r in rows:
        mark = "" if r["finished"] else "*"
        parts.append((f"{r['solved_at']:,}" if r["done"] else f"{len(r['achieved'])}/{r['total']}")
                     + mark)
    return " ; ".join(parts)


def table(data: dict, budget: int) -> str:
    tasks, lives = data["tasks"], data["lives"]
    head = (["memory of the diamond life", "it had reached", "it had written"]
            + tasks + ["solved", "mean steps to solve", f"mean steps to {OPENING}", "mean turns"])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for mem in data["memory"]:
        t = mem["t"]
        rows = [r for task in tasks for r in lives.get(f"{t}/{task}", [])]
        solved = sum(r["done"] for r in rows)
        # a task the budget cut short counts the budget: a lower bound on its solve step
        to_solve = [r["solved_at"] if r["done"] else budget for r in rows]
        opening = [r["opening_at"] if r["opening_at"] is not None else budget for r in rows]
        mean = lambda xs: f"{statistics.mean(xs):,.0f}" if xs else "--"  # noqa: E731
        bound = ">=" if rows and solved < len(rows) else ""
        lines.append("| " + " | ".join([
            "none" if t == 0 else f"first {t:,} steps",
            "--" if t == 0 else f"{mem['milestones']}/10",
            "--" if t == 0 else (", ".join(mem["written"]) or "no script of its own")
            + f"; guide {mem['guide_bytes']:,} B, notes {mem['notes_bytes']:,} B",
            *[_cell(lives.get(f"{t}/{task}"), budget) for task in tasks],
            f"{solved}/{len(rows)}" if rows else "--",
            bound + mean(to_solve), mean(opening), mean([r["turns"] for r in rows]),
        ]) + " |")
    notes = [f"Probe budget {budget:,} steps; a cell is the step of the task's last milestone, "
             f"or milestones banked when the budget ran out (counted as {budget:,} in the mean, "
             "a lower bound). `*` = the life has not finished."]
    flagged = [r["arm"] for rows in lives.values() for r in rows
               if r["refused"] or r["errors"] or r["turns_failed"]]
    if flagged:
        notes.append("Lives with refused or failed model turns (their steps include no-ops): "
                     + ", ".join(flagged) + ".")
    src = data["source"]
    if src:
        notes.append(f"Source life: {len(src['achieved'])}/{src['total']} milestones in "
                     f"{src['steps'] + 1:,} steps, {src['turns']} turns.")
    return "\n".join(lines) + "\n\n" + "\n".join(notes) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."), help="the MCU directory of the run")
    ap.add_argument("--tag", default="sr")
    ap.add_argument("--budget", type=int, default=6000)
    ap.add_argument("--json", type=Path, default=None, help="also write every life's row here")
    args = ap.parse_args()
    data = collect(args.root.resolve(), args.tag)
    if not data["lives"]:
        sys.exit(f"no probe lives named {args.tag}_<task>_t<step> under {args.root}/output")
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(table(data, args.budget))


if __name__ == "__main__":
    main()
