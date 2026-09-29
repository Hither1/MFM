#!/usr/bin/env python3
"""Score an A-B-A campaign, per leg.

MrSteve's own `scripts/get_stats.py` reduces an episode to `total_tasks == success_tasks`
-- one all-or-nothing bit. That throws away the only comparison these tasks are built to
make. An A-B-A episode has two retrievals in it and they are not the same experiment:

    goal 1 -> goal 2   the agent needed a resource it walked past while working on
                       something else. Incidental encoding: it had no reason to note the
                       place at the time. This is the number to read.
    goal 2 -> goal 3   the agent needed a resource that WAS its goal when it first found
                       it. Deliberate re-retrieval, and much the easier of the two.

Both are reported as conditionals, because an episode that never reached goal 1 says
nothing about retrieval at all and averaging it in only dilutes the signal.

Reads whatever the arms wrote: `worldmodel_report.json` (mfm / vista / arc / logbook /
direct) or `prolong_milestones.json` (prolong / plmfm). Both carry `MilestoneLedger.summary()`.

    scripts/aba_stats.py output/aba_mfm output/aba_vista output/aba_arc output/aba_plmfm
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPORTS = ("worldmodel_report.json", "prolong_milestones.json")


def load_episodes(root: Path) -> list[dict]:
    """Every episode report under `root`, as its milestone summary."""
    out = []
    for name in REPORTS:
        for path in sorted(root.rglob(name)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"  ! unreadable {path}: {exc}", file=sys.stderr)
                continue
            summary = data.get("milestones")
            if isinstance(summary, dict) and summary.get("order"):
                summary = dict(summary)
                summary["_path"] = str(path)
                summary["_steps"] = data.get("steps")
                out.append(summary)
    return out


def _pct(num: int, den: int) -> str:
    return f"{num}/{den}" + (f" ({100 * num / den:.0f}%)" if den else "")


def stats(episodes: list[dict]) -> dict:
    """Per-leg counts, the two conditionals, and how far apart the legs fell."""
    order = episodes[0]["order"]
    n = len(episodes)
    reached = [0] * len(order)
    steps: list[list[int]] = [[] for _ in order]
    gaps: list[list[int]] = [[] for _ in order]

    for ep in episodes:
        achieved = ep.get("achieved") or {}
        prev_step = None
        for i, ident in enumerate(order):
            if ident not in achieved:
                break
            reached[i] += 1
            step = achieved[ident]
            steps[i].append(step)
            if prev_step is not None:
                gaps[i].append(step - prev_step)
            prev_step = step

    def med(xs):
        return round(statistics.median(xs)) if xs else None

    return {
        "n": n,
        "order": order,
        "reached": reached,
        "complete": reached[-1] if reached else 0,
        "median_step": [med(s) for s in steps],
        "median_gap": [med(g) for g in gaps],
        # The retrieval rates. Conditional on having got that far -- see the docstring.
        "conditional": [
            (reached[i], reached[i - 1]) for i in range(1, len(order))
        ],
    }


def report(label: str, s: dict) -> None:
    order, n = s["order"], s["n"]
    print(f"\n{label}")
    print(f"  episodes                {n}")
    print(f"  all {len(order)} goals" + " " * 14 + f"{_pct(s['complete'], n)}")
    print("  per goal:")
    for i, ident in enumerate(order):
        step = s["median_step"][i]
        gap = s["median_gap"][i]
        line = f"    {i + 1}. {ident:<12} {_pct(s['reached'][i], n):>14}"
        if step is not None:
            line += f"   median step {step:>6}"
        if gap is not None:
            line += f"   +{gap} since previous"
        print(line)
    print("  retrieval (conditional on reaching the previous goal):")
    names = ["incidental — the resource was passed while working on something else",
             "deliberate — the resource was the active goal when first found"]
    for i, (num, den) in enumerate(s["conditional"]):
        kind = names[i] if i < len(names) else ""
        leg = f"{order[i]} -> {order[i + 1]}"
        print(f"    {leg:<28} {_pct(num, den):>14}   {kind}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rootdir", nargs="+", type=Path,
                    help="one arm's output directory per argument")
    ap.add_argument("--json", action="store_true", help="machine-readable instead")
    args = ap.parse_args(argv)

    out = {}
    for root in args.rootdir:
        episodes = load_episodes(root)
        if not episodes:
            print(f"\n{root}: no episode reports found "
                  f"(looked for {' or '.join(REPORTS)})", file=sys.stderr)
            continue
        orders = {tuple(e["order"]) for e in episodes}
        if len(orders) > 1:
            print(f"\n{root}: episodes disagree about the goal list {orders}; "
                  f"these are not the same task and are not comparable", file=sys.stderr)
            continue
        s = stats(episodes)
        out[str(root)] = s
        if not args.json:
            report(str(root), s)

    if args.json:
        print(json.dumps(out, indent=2))
    return 0 if out else 1


if __name__ == "__main__":
    raise SystemExit(main())
