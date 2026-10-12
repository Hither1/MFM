"""Summarise one arm across task orders: the seeds of the KiCad table.

    python gym_codex/kicad_task_orders.py <run dir of seed 0> <run dir of seed 1> ...

Each argument is a run dir with `results.jsonl` and, for a run launched with
`--task-order-seed`, `task_order.json` (a run without it took the registry order,
position = sorted-id rank). Prints, per run, the seed, mean official reward and mean
steps; per task, the reward across runs; and per position third, the mean reward and
steps pooled over runs -- for an arm that carries memory across tasks, whether later
tasks cost fewer steps. Official reward only; pass `--relaxed` to read `relaxed` from
rows that carry it.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def load(run: Path, key: str) -> tuple[int | None, list[dict]]:
    rows = [json.loads(l) for l in (run / "results.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get(key) is not None]
    order = run / "task_order.json"
    if order.exists():
        rec = json.loads(order.read_text())
        seed, ids = rec.get("task_order_seed"), rec["task_ids"]
    else:
        seed, ids = None, sorted(r["task_id"] for r in rows)
    pos = {t: i for i, t in enumerate(ids)}
    for r in rows:
        r["_pos"] = r.get("order_index") if r.get("order_index") is not None else pos.get(r["task_id"])
    return seed, rows


def third(pos: int, n: int) -> int:
    return min(2, pos * 3 // n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--relaxed", action="store_true", help="score = row['relaxed'] instead of reward")
    a = ap.parse_args()
    key = "relaxed" if a.relaxed else "reward"

    runs = [(r.name, *load(r, key)) for r in a.runs]
    print(f"{'run':44s} {'seed':>6s} {'n':>3s} {'mean':>6s} {'steps':>6s}")
    for name, seed, rows in runs:
        print(f"{name:44s} {str(seed):>6s} {len(rows):3d} "
              f"{statistics.fmean(r[key] for r in rows):6.3f} "
              f"{statistics.fmean(r['steps'] for r in rows):6.1f}")
    means = [statistics.fmean(r[key] for r in rows) for _, _, rows in runs]
    if len(means) > 1:
        print(f"{'across runs':44s} {'':>6s} {'':>3s} {statistics.fmean(means):6.3f} "
              f"sd {statistics.stdev(means):.3f} range {min(means):.3f}-{max(means):.3f}")

    # per task: reward across runs
    tasks = sorted({r["task_id"] for _, _, rows in runs for r in rows})
    by = {(name, r["task_id"]): r for name, _, rows in runs for r in rows}
    print(f"\n{'task':10s} " + " ".join(f"{s if s is not None else 'reg':>5}" for _, s, _ in runs) + "   moves")
    moved = 0
    for t in tasks:
        vals = [by.get((name, t), {}).get(key) for name, _, _ in runs]
        have = [v for v in vals if v is not None]
        flip = len(have) > 1 and max(have) - min(have) > 1e-9
        moved += flip
        print(f"{t:10s} " + " ".join(f"{v:5.2f}" if v is not None else "    -" for v in vals)
              + ("   *" if flip else ""))
    print(f"{moved}/{len(tasks)} tasks take a different score in at least one order")

    # by position third, pooled
    print(f"\n{'third':6s} {'n':>4s} {'mean':>6s} {'steps':>6s}   (pooled over the shuffled runs; registry-order run listed apart)")
    for label, sel in (("shuffled", [x for x in runs if x[1] is not None]),
                       ("registry", [x for x in runs if x[1] is None])):
        if not sel:
            continue
        print(f"-- {label}")
        for k in range(3):
            rs = [r for _, _, rows in sel for r in rows
                  if r["_pos"] is not None and third(r["_pos"], len(rows)) == k]
            if rs:
                print(f"{k + 1:6d} {len(rs):4d} {statistics.fmean(r[key] for r in rs):6.3f} "
                      f"{statistics.fmean(r['steps'] for r in rs):6.1f}")


if __name__ == "__main__":
    main()
