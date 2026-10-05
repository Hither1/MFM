#!/usr/bin/env python3
"""A skills-only seed for `--install-scripts` from a published life's `mine/` (the
MCUData dataset, `release-runs/agent-written/<life>/`).

    hf_skill_seed.py <agent-written dir> <life> --out DIR [--exclude a,b] [--check]

What goes into the seed is only the scripts the model wrote: by the dataset's own
per-file `origin` (`release-runs/files.csv`, a byte comparison against the examples of
the life's era), the files under mine/procedures, mine/reflexes and mine/tools whose
origin is `new`, `earlier life's, *` or `shipped example, edited`. Unchanged copies of
the shipped examples are left out (every probe copies those itself), and so are the
notes, the guide and the images: this is the skills row, not the diary. `--exclude`
drops named scripts (place-bound ones, ones that read state the harness does not give).

The seed is a directory `previous.lives_of` accepts (a `logs.txt` marker naming the
life) with no `skills/`, so `previous.install_scripts` installs everything in it.
`.seed.json` records what was taken from where.

`--check` runs every procedure once under the harness's own runner (mcu_worldmodel.own)
on each of three plausible states (underground in a tunnel, on the surface, at a gravel
patch with the shovel held) and sorts the outcomes: `ok` (a plan came out), `refused`
(the script declined on a precondition it names: the pose, a missing argument -- the
guard working as written) and `CRASH` (a Python error: the script cannot run here, e.g.
it reads a state key the harness does not give). Only crashes argue for exclusion; a
script refused in all three states is reported so place-bound ones stand out.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIRS = ("procedures", "reflexes", "tools")
TAKEN = ("new", "earlier life's, unchanged", "earlier life's, edited", "shipped example, edited")

#: The states a check runs on; `underground`: on stone at y 12 in a 1x2 tunnel facing
#: north, a stone pickaxe in slot 1, torches in slot 2, cobblestone in slot 3, a shovel
#: in 4 (the others derive from it below).
CHECK_STATE = {
    "step": 1000, "max_steps": 4000,
    "pos": {"x": -5853.5, "y": 12.0, "z": -3781.5, "pitch": 8.0, "yaw": 0.0},
    "health": 20.0, "food": 18.0,
    "inventory": {"stone_pickaxe": 1, "torch": 16, "cobblestone": 40, "iron_shovel": 1,
                  "crafting_table": 1, "oak_log": 6, "gravel": 9},
    "hotbar": [{"slot": 0, "item": "stone_pickaxe", "n": 1}, {"slot": 1, "item": "torch", "n": 16},
               {"slot": 2, "item": "cobblestone", "n": 40}, {"slot": 3, "item": "iron_shovel", "n": 1},
               {"slot": 4, "item": "crafting_table", "n": 1}, {"slot": 5, "item": "oak_log", "n": 6},
               {"slot": 6, "item": "gravel", "n": 9}, {"slot": 7, "item": None, "n": 0},
               {"slot": 8, "item": None, "n": 0}],
    "gui_open": False, "dimension": "the Overworld",
}


def _state(name: str) -> dict:
    import copy
    st = copy.deepcopy(CHECK_STATE)
    if name == "surface":
        st["pos"].update({"y": 68.0, "pitch": 0.0, "yaw": 45.0})
        st["hotbar"][1] = {"slot": 1, "item": "stone_sword", "n": 1}
        st["inventory"].update({"stone_sword": 1, "stick": 8})
        st["hotbar"][7] = {"slot": 7, "item": "stick", "n": 8}
    elif name == "gravel":
        st["pos"].update({"y": 68.0, "pitch": 45.0, "yaw": 0.0})
        st["hotbar"][0], st["hotbar"][3] = st["hotbar"][3], st["hotbar"][0]   # shovel held
        st["hotbar"][0]["slot"], st["hotbar"][3]["slot"] = 0, 3
    return st


CHECK_STATES = ("underground", "surface", "gravel")
_CRASH = ("Error:", "Error ", "Traceback", "exception", "timed out", "printed nothing",
          "not a plan")


def _kind(why: str | None) -> str:
    if why is None:
        return "ok"
    return "CRASH" if any(k in why for k in _CRASH) else "refused"


def origins(files_csv: Path, life: str) -> dict[str, str]:
    with open(files_csv, newline="", encoding="utf-8") as fh:
        return {r["path"]: r["origin"] for r in csv.DictReader(fh) if r["life"] == life}


def build(root: Path, life: str, out: Path, exclude: set[str]) -> dict:
    src = root / life / "mine"
    if not src.is_dir():
        raise SystemExit(f"no mine/ under {root / life}")
    if out.exists():
        raise SystemExit(f"{out} exists")
    org = origins(root.parent / "files.csv", life)
    taken, left = [], []
    for d in SCRIPT_DIRS:
        for p in sorted((src / d).glob("*.py")):
            rel = f"mine/{d}/{p.name}"
            o = org.get(rel, "unknown")
            if p.stem in exclude:
                left.append({"path": rel, "origin": o, "why": "excluded"})
            elif o in TAKEN:
                (out / "mine" / d).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, out / "mine" / d / p.name)
                taken.append({"path": rel, "origin": o})
            else:
                left.append({"path": rel, "origin": o, "why": "a shipped example, unchanged"
                             if o.startswith("shipped") else "origin unknown"})
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs.txt").write_text(f"skills of {life} (MCUData release-runs/agent-written), "
                                  f"installed by --install-scripts; no record carried\n")
    info = {"life": life, "source": str(root / life), "taken": taken, "left": left}
    (out / ".seed.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return info


def check(out: Path, mcu: Path) -> list[dict]:
    sys.path.insert(0, str(mcu))
    from mcu_worldmodel import own
    rows = []
    for proc in own.scan(out).values():
        outcomes = {}
        for sname in CHECK_STATES:
            plan, why = own.run(proc, out, _state(sname), {})
            n = None
            if plan:
                try:
                    n = len(json.loads(plan).get("actions", []))
                except (ValueError, AttributeError):
                    why = "printed something that is not a plan"
            outcomes[sname] = {"kind": _kind(why), "entries": n, "why": why}
        kinds = {o["kind"] for o in outcomes.values()}
        verdict = ("CRASH" if "CRASH" in kinds else "ok" if "ok" in kinds else "refused everywhere")
        rows.append({"name": proc.name, "verdict": verdict, "states": outcomes})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="the release-runs/agent-written directory")
    ap.add_argument("life")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exclude", default="", help="comma-separated script names to leave out")
    ap.add_argument("--check", action="store_true", help="run every procedure once and report")
    ap.add_argument("--mcu", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()
    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    info = build(args.root.resolve(), args.life, args.out, exclude)
    print(f"{args.life}: {len(info['taken'])} script(s) taken, {len(info['left'])} left out")
    for t in info["taken"]:
        print(f"   + {t['path']}  ({t['origin']})")
    for l in info["left"]:
        print(f"   - {l['path']}  ({l['why']})")
    if args.check:
        rows = check(args.out, args.mcu)
        (args.out / ".check.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        for r in rows:
            cells = []
            for sname, o in r["states"].items():
                cells.append(f"{sname}: " + (f"ok ({o['entries']} entries)" if o["kind"] == "ok"
                                             else f"{o['kind']}: {(o['why'] or '')[:70]}"))
            print(f"   {r['verdict']:18s} {r['name']:26s} | " + " | ".join(cells))
        bad = [r["name"] for r in rows if r["verdict"] == "CRASH"]
        print(f"   crashes: {bad or 'none'}; refused everywhere: "
              f"{[r['name'] for r in rows if r['verdict'] == 'refused everywhere'] or 'none'}")


if __name__ == "__main__":
    main()
