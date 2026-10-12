#!/usr/bin/env python3
r"""Score nether-portal runs: where the obsidian actually went.

The task asks one thing: arrange the blocks into the right shape. The agent is handed a
full stack, so nothing is scarce and nothing can leave it stuck; the milestone ledger's
two bits -- a block was placed, the Nether was reached -- are not the measurement.

The measurement is `portal_report.json`, written by `mcu_worldmodel.portal_probe` from
the engine's privileged voxel channel, and the numbers in it that no statistic an agent
can read will ever give you:

    matched at first strike   how many of the ten required cells held obsidian the
                              first time the flint and steel was used. An agent that
                              knows where its blocks are strikes at 10/10.
    best frame                the closest the build ever came, and what was missing.
    blocked interior          blocks left standing in the 2x3 that must be air. This is
                              the error an agent cannot see and cannot name.
    placed into unused cells  obsidian put in a cell the frame does not use.
    repeat strikes            the same wrong geometry lit again. In an early run one
                              agent struck five times at exactly 6/10 with the same two
                              interior blocks each time -- the clearest evidence that
                              nothing available to it said which cell was wrong.

NOTE: the probe is a green-side callback, so the report lands under the green server's
own `output/<timestamp>_<pid>/<task>/`, not beside the arm's episode output. Map an arm
to its directory with `grep '\[portal\] wrote' logs/<arm>_green.log`.

    scripts/portal_stats.py output/2026*_*/nether_portal
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REQUIRED_CELLS = 10


def load_episodes(root: Path) -> list[dict]:
    """Every `portal_report.json` under `root`, with the sibling run report folded in."""
    out = []
    for path in sorted(root.rglob("portal_report.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  ! unreadable {path}: {exc}", file=sys.stderr)
            continue
        data["_path"] = str(path)
        data["_run"] = _run_report(path.parent)
        data["_entries"] = _log_entries(path.parent)
        out.append(data)
    return out


def _run_report(episode_dir: Path) -> dict:
    """`worldmodel_report.json` beside the portal report, for turns and milestones."""
    for name in ("worldmodel_report.json",):
        for path in (episode_dir / name, *episode_dir.rglob(name)):
            if path.is_file():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return {}
    return {}


def _log_entries(episode_dir: Path) -> int | None:
    """Lines in the arm's own `logs.txt`, the size of the trace it had to search.

    The dragon run this task comes from wrote 812 entries between picking up the
    obsidian and standing in the Nether; on a task that is only the portal, this is
    that number with nothing else in it.
    """
    best = None
    for path in episode_dir.rglob("logs.txt"):
        try:
            n = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        best = n if best is None else max(best, n)
    return best


def _med(xs: list[float]) -> str:
    return f"{statistics.median(xs):.0f}" if xs else "-"


def _pct(num: int, den: int) -> str:
    return f"{num}/{den}" + (f" ({100 * num / den:.0f}%)" if den else "")


def stats(episodes: list[dict]) -> dict:
    n = len(episodes)
    lit = [e for e in episodes if e.get("first_lit_step") is not None]
    complete = [e for e in episodes if e.get("first_complete_step") is not None]
    nether = [e for e in episodes if e.get("dimension_change_step") is not None]

    first_match, best_match, placed, mined, wasted, ignitions = [], [], [], [], [], []
    blocked, repeats, steps_to_lit, entries, turns = [], [], [], [], []
    for e in episodes:
        counts = e.get("counts") or {}
        best = e.get("best_frame") or {}
        igs = e.get("ignitions") or []
        if igs:
            first_match.append(igs[0].get("fit", {}).get("matched", 0))
        best_match.append(best.get("matched", 0))
        placed.append(counts.get("obsidian_placed", 0))
        mined.append(counts.get("obsidian_mined", 0))
        wasted.append(counts.get("obsidian_placed_into_unused_cells", 0))
        ignitions.append(counts.get("ignitions", 0))
        blocked.append(len(best.get("blocked_interior") or []))
        # How often a strike repeated a geometry an earlier strike had already failed
        # with. The point of the column: an agent that could see what was wrong would
        # not fire the same frame twice.
        shapes = [(g.get("fit", {}).get("matched"),
                   len(g.get("fit", {}).get("blocked_interior") or [])) for g in igs]
        repeats.append(len(shapes) - len(set(shapes)) if shapes else 0)
        if e.get("first_lit_step") is not None:
            steps_to_lit.append(e["first_lit_step"])
        if e.get("_entries"):
            entries.append(e["_entries"])
        t = ((e.get("_run") or {}).get("turns") or {}).get("act")
        if t is not None:
            turns.append(t)

    unreadable = sum(1 for e in episodes if e.get("unreadable_samples"))
    return {
        "episodes": n,
        "complete_frame": len(complete), "lit": len(lit), "nether": len(nether),
        "first_match": first_match, "best_match": best_match,
        "placed": placed, "mined": mined, "wasted": wasted, "ignitions": ignitions,
        "blocked": blocked, "repeats": repeats, "steps_to_lit": steps_to_lit,
        "entries": entries, "turns": turns,
        "unreadable": unreadable,
    }


def report(label: str, s: dict) -> None:
    n = s["episodes"]
    print(f"\n{label}  ({n} episode{'s' if n != 1 else ''})")
    if not n:
        return
    if s["unreadable"]:
        print(f"  !! {s['unreadable']} episode(s) had an unreadable voxel channel -- "
              f"their geometry columns are meaningless")
    print(f"  legal frame built       {_pct(s['complete_frame'], n)}")
    print(f"  portal lit              {_pct(s['lit'], n)}   median step {_med(s['steps_to_lit'])}")
    print(f"  reached the Nether      {_pct(s['nether'], n)}")
    print(f"  cells right at strike 1 median {_med(s['first_match'])}/{REQUIRED_CELLS}"
          f"   best frame at end median {_med(s['best_match'])}/{REQUIRED_CELLS}")
    print(f"  blocks left in interior median {_med(s['blocked'])}"
          f"   placed into cells the frame does not use: median {_med(s['wasted'])}")
    print(f"  strikes                 median {_med(s['ignitions'])}"
          f"   of which repeated an already-failed shape: median {_med(s['repeats'])}")
    print(f"  obsidian placed         median {_med(s['placed'])}"
          f"   mined back: median {_med(s['mined'])}")
    if s["turns"] or s["entries"]:
        print(f"  act turns median {_med(s['turns'])}   log entries median {_med(s['entries'])}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rootdir", nargs="+", type=Path,
                    help="one directory per arm; searched recursively for portal_report.json")
    ap.add_argument("--json", action="store_true", help="machine-readable instead")
    ap.add_argument("--cells", action="store_true",
                    help="also print each episode's placement history, cell by cell")
    args = ap.parse_args(argv)

    out = {}
    for root in args.rootdir:
        episodes = load_episodes(root)
        out[root.name] = stats(episodes)
        if not args.json:
            report(root.name, out[root.name])
            if args.cells:
                for e in episodes:
                    print(f"    {e['_path']}")
                    for p in e.get("placements", []):
                        print(f"      step {p['step']:>6}  placed {p['block'].split(':')[-1]:<14}"
                              f" at {tuple(p['cell'])}")
                    for r in e.get("removals", []):
                        print(f"      step {r['step']:>6}  removed {r['block'].split(':')[-1]:<13}"
                              f" at {tuple(r['cell'])}")
    if args.json:
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
