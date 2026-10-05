#!/usr/bin/env python3
"""The skill-reuse table, second design (slurm/skill_reuse2.sbatch): how fast the tail of
the iron chain is run in a new world from no memory, from the memory of one diamond
life, of two, and of two with every agent-written script removed.

    skill_reuse2_table.py [--root MCU] [--tag sr2] [--budget 4000] [--json out.json]

Rows are what was carried; columns the tail tasks. A cell is the step at which the
task's last milestone was banked, or `k/n` when the budget ran out first; replicates are
joined with `;`. The last column counts the probe's calls of a CARRIED agent-written
procedure, which is what ties a faster row to the skills rather than to the diary. Every
number is read from files the lives wrote (see skill_reuse_table.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory_at  # noqa: E402
from skill_reuse_table import _json, life  # noqa: E402

ROWS = ("none", "skills", "life1", "life2", "life2_nosk")
LABEL = {"none": "no memory", "skills": "scripts of lives 1+2 only (no notes, no record)",
         "life1": "diamond life 1", "life2": "diamond lives 1+2",
         "life2_nosk": "lives 1+2, scripts removed"}
#: Where a row's scripts come from when the row has no seed dir of its own.
SEED_OF = {"skills": "life2"}
#: The probe tasks, named so a smoke life (<tag>_smoke_<task>_<row>) is not a probe.
TASKS = ("iron_shield_tail", "shears_tail", "bucket_tail", "coal_torches_tail", "cook_meat_tail",
         "iron_shield_vein")
ARM = re.compile(r"^(?P<tag>.+?)(?:_r(?P<rep>\d+))?_(?P<task>" + "|".join(TASKS)
                 + r")_(?P<row>" + "|".join(ROWS) + r")$")
#: The example procedures every life finds under skills/procedures/scripts: a call of
#: any other own procedure is a call of a script some life wrote.
SHIPPED_PROCEDURES = {"aim_speckles", "shaft_down", "stair_step", "strip_segment", "torch_wall"}
#: The milestone that decided every probe: no life that mined iron ore failed to smelt it.
BINDING = "mine_iron_ore"


def seed_of(root: Path, tag: str, row: str) -> Path | None:
    p = root / "output" / f"{tag}_mem" / SEED_OF.get(row, row)
    return p if p.is_dir() else None


def _log_key(life: Path) -> str | None:
    try:
        return hashlib.sha1((life / "logs.txt").read_bytes()).hexdigest()
    except OSError:
        return None


_REPORTS: dict[Path, dict] = {}


def _source_reports(root: Path) -> dict:
    """The reports of the source lives (output/*_src_*), by the hash of their log."""
    if root not in _REPORTS:
        _REPORTS[root] = {
            _log_key(ep / "memory"): _json(ep / "worldmodel_report.json") or {}
            for ep in sorted((root / "output").glob("*_src_*/episode_001"))}
    return _REPORTS[root]


def memory_row(root: Path, tag: str, row: str) -> dict:
    """What the row's seed brought: per life, its milestones, the scripts the model
    wrote and the size of its working notes."""
    seed = seed_of(root, tag, row)
    if row == "none" or seed is None:
        return {"row": row, "lives": []}
    lives = []
    for i, d in enumerate(memory_at.lives_of(seed), 1):
        # a carried life is a linked copy: its report is the one of the source life whose
        # log has the same bytes
        rep = _source_reports(root).get(_log_key(d), {})
        ms = (rep.get("milestones") or {}).get("achieved") or {}
        own = memory_at.own_files(d)
        size = lambda n: (d / "mine" / n).stat().st_size if (d / "mine" / n).exists() else 0  # noqa: E731
        lives.append({"life": i, "milestones": len(ms) or None, "own": own,
                      "working_bytes": size("working.md"), "guide_bytes": size("GUIDE.md"),
                      "notes_bytes": size("notes.md")})
    return {"row": row, "lives": lives}


def carried_calls(r: dict, carried: set[str]) -> int:
    """The probe's calls of procedures a carried life wrote (by script stem)."""
    calls = ((r.get("own") or {}).get("calls") or {})
    return sum(int(n) for name, n in calls.items() if name in carried)


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
        r["finished"] = (root / "logs" / f"{run.name}_result.json").exists()
        r["rep"] = int(m.group("rep") or 1)
        # None: the life ran without --install-carried (only right for the none row)
        r["installed"] = (_json(run / "episode_001" / "worldmodel_report.json") or {}).get("installed")
        lives.setdefault((m.group("row"), m.group("task")), []).append(r)
    rows = [r for r in ROWS if any(k[0] == r for k in lives)]
    tasks = [t for t in TASKS if any(k[1] == t for k in lives)]
    memory = {r: memory_row(root, tag, r) for r in rows}
    for (row, _), rs in lives.items():
        carried = {Path(k).stem for l in memory[row]["lives"] for k, v in l["own"].items()
                   if v == "written" and k.startswith("procedures/")}
        for r in rs:
            r["carried_calls"] = carried_calls(r, carried)
            # calls of any procedure a life wrote, the probe itself included
            r["written_calls"] = {n: int(c) for n, c in ((r.get("own") or {}).get("calls") or {}).items()
                                  if n not in SHIPPED_PROCEDURES}
    # the last milestone every task shares: the end of the common chain
    orders = [rs[0]["order"] for rs in lives.values() if rs]
    shared = None
    if orders:
        for i, name in enumerate(orders[0]):
            if all(len(o) > i and o[i] == name for o in orders):
                shared = name
            else:
                break
    sources = {a: life(out / a) for a in (f"sr_src_diamond", f"{tag}_src_diamond_l2")}
    # the iron column only where every task shown has that milestone
    binding = BINDING if orders and all(BINDING in o for o in orders) else None
    return {"tag": tag, "rows": rows, "tasks": tasks, "shared": shared, "binding": binding,
            "memory": memory,
            "sources": {k: v for k, v in sources.items() if v},
            "lives": {f"{row}/{task}": rs for (row, task), rs in sorted(lives.items())}}


def _cell(rs: list[dict] | None) -> str:
    if not rs:
        return "--"
    return " ; ".join((f"{r['solved_at']:,}" if r["done"] else f"{len(r['achieved'])}/{r['total']}")
                      + ("" if r["finished"] else "*") for r in rs)


def _carried(mem: dict) -> str:
    if not mem["lives"]:
        return "--"
    parts = []
    for l in mem["lives"]:
        own = [f"{Path(k).stem} ({v})" for k, v in l["own"].items()]
        parts.append(f"life {l['life']}: {l['milestones'] or '?'}/10, "
                     f"{', '.join(own) if own else 'no script of its own'}, "
                     f"working {l['working_bytes'] / 1024:.0f} KB")
    return "; ".join(parts)


def table(data: dict, budget: int) -> str:
    tasks, lives, shared = data["tasks"], data["lives"], data["shared"]
    binding = data.get("binding")
    head = (["carried", "what it held"] + tasks
            + ["solved"] + ([f"reached {binding}"] if binding else []) + ["mean steps to solve"]
            + ([f"mean steps to {shared}"] if shared else [])
            + ["mean turns", "calls of a carried script", "calls of a script written in the probe"])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    mean = lambda xs: f"{statistics.mean(xs):,.0f}" if xs else "--"  # noqa: E731
    for row in data["rows"]:
        rs = [r for task in tasks for r in lives.get(f"{row}/{task}", [])]
        solved = sum(r["done"] for r in rs)
        to_solve = [r["solved_at"] if r["done"] else budget for r in rs]
        to_shared = [r["achieved"].get(shared, budget) for r in rs] if shared else []
        bound = ">=" if rs and solved < len(rs) else ""
        lines.append("| " + " | ".join([
            LABEL[row], _carried(data["memory"][row]),
            *[_cell(lives.get(f"{row}/{task}")) for task in tasks],
            f"{solved}/{len(rs)}" if rs else "--",
            *([f"{sum(binding in r['achieved'] for r in rs)}/{len(rs)}" if rs else "--"] if binding else []),
            bound + mean(to_solve),
            *([mean(to_shared)] if shared else []),
            mean([r["turns"] for r in rs]), str(sum(r["carried_calls"] for r in rs)),
            str(sum(sum(r["written_calls"].values()) for r in rs)
                - sum(r["carried_calls"] for r in rs)),
        ]) + " |")
    notes = [f"Probe budget {budget:,} steps from a handed-over opening (stone pickaxe, table, "
             f"8 cobblestone, 6 logs); a cell is the step of the task's last milestone, or "
             f"milestones banked when the budget ran out (counted as {budget:,} in the mean, "
             "a lower bound). `*` = the life has not finished."]
    flagged = [r["arm"] for rs in lives.values() for r in rs
               if r["refused"] or r["errors"] or r["turns_failed"]]
    if flagged:
        notes.append("Lives with refused or failed model turns (their steps include no-ops): "
                     + ", ".join(flagged) + ".")
    uninstalled = [r["arm"] for key, rs in lives.items() for r in rs
                   if not key.startswith("none/") and r["installed"] is None]
    if uninstalled:
        notes.append("WARNING -- carried lives that ran WITHOUT --install-carried (another "
                     "design; do not average them in): " + ", ".join(uninstalled) + ".")
    installed = sorted({f"{i['path']} (life {i['life']})" for rs in lives.values() for r in rs
                        for i in (r["installed"] or [])})
    if installed:
        notes.append("Installed into the probes' mine/: " + ", ".join(installed) + ".")
    for name, src in data["sources"].items():
        notes.append(f"Source {name}: {len(src['achieved'])}/{src['total']} milestones in "
                     f"{src['steps'] + 1:,} steps, {src['turns']} turns.")
    return "\n".join(lines) + "\n\n" + "\n".join(notes) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."), help="the MCU directory of the run")
    ap.add_argument("--tag", default="sr2")
    ap.add_argument("--budget", type=int, default=4000)
    ap.add_argument("--json", type=Path, default=None, help="also write every life's row here")
    ap.add_argument("--tasks", nargs="+", choices=TASKS, default=None,
                    help="only these probe tasks (default: every one that has a life)")
    args = ap.parse_args()
    data = collect(args.root.resolve(), args.tag, args.tasks)
    if not data["lives"]:
        sys.exit(f"no probe lives named {args.tag}_<task>_<row> under {args.root}/output")
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(table(data, args.budget))


if __name__ == "__main__":
    main()
