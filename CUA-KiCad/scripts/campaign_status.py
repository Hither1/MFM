#!/usr/bin/env python3
"""Progress and ETA for every cell of a campaign, read off the checkpoints.

The cells are separate processes with separate logs and no shared state, which is
what makes them cheap to run and awkward to watch. Their checkpoints are the one
thing they all write per question, so that is what this reads.

    python scripts/campaign_status.py runs/qwen35_v1 [--n 300]
"""
from __future__ import annotations

import argparse
import json
import os
import time

CELLS = ["bcp_default", "bcp_hypothesis", "bcp_prolong"]


def _read(path: str) -> list[dict]:
    """Both checkpoint shapes this repository has written.

    The cells append one JSON object per line. An arm whose memory is part of the
    state a resume has to restore instead rewrites a single document --
    {"limit":..., "results":[...], "memory":...} -- atomically after every question,
    because an append-only log cannot express a memory that changes. Read as JSONL it
    looks like one answered question forever.
    """
    if not os.path.exists(path):
        return []
    text = open(path).read()
    stripped = text.lstrip()
    if stripped.startswith("{") and '"results"' in stripped[:200]:
        try:
            return json.loads(text).get("results", [])
        except json.JSONDecodeError:
            return []             # mid-rename; the next poll will see it
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue              # a line cut off mid-write; the run will redo it
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--n", type=int, default=300, help="Questions per cell.")
    args = ap.parse_args()

    now = time.time()
    print(f"{'cell':<22}{'done':>9}{'acc':>8}{'age':>8}{'rate':>11}{'eta':>9}")
    for cell in CELLS:
        base = os.path.join(args.run_dir, cell)
        # The evaluators derive the name from --output (`result.json.checkpoint.jsonl`);
        # an explicit --checkpoint path is the other shape seen.
        cands = [os.path.join(base, "result.json.checkpoint.jsonl"),
                 os.path.join(base, "result.checkpoint.jsonl")]
        ckpt = next((c for c in cands if os.path.exists(c)), cands[0])
        rows = _read(ckpt)
        if not rows:
            state = "done" if os.path.exists(os.path.join(base, "result.json")) else "-"
            print(f"{cell:<22}{state:>9}")
            continue
        n = len(rows)
        # `correct` is a bool in every arm's record; an older checkpoint may key it
        # differently, so fall back rather than crash on a cell that is running fine.
        acc = sum(bool(r.get("correct", r.get("is_correct"))) for r in rows) / n
        # Wall-clock rate from the checkpoint's own mtime, not from elapsed_sec: under
        # concurrency the per-question times overlap and would sum to more than the run.
        # run_cell.sh stamps started_at; without it fall back to the oldest thing in
        # the cell directory, which is at worst an over-estimate of the age.
        stamp = os.path.join(base, "started_at")
        if os.path.exists(stamp):
            started = float(open(stamp).read().strip())
        else:
            started = min(os.path.getmtime(os.path.join(base, f))
                          for f in os.listdir(base)) if os.listdir(base) else now
        age = max(1e-9, os.path.getmtime(ckpt) - started)
        # Only what this process did: a resumed cell inherits records it did not run.
        try:
            resumed = int(open(os.path.join(base, "resumed_from")).read().strip() or 0)
        except (OSError, ValueError):
            resumed = 0
        rate = (n - resumed) / age * 60 if age > 1 else float("nan")
        left = max(0, args.n - n)
        eta = left / rate if rate == rate and rate > 0 else float("nan")
        stale = now - os.path.getmtime(ckpt)
        mark = "  (stale)" if stale > 900 else ""
        print(f"{cell:<22}{n:>4}/{args.n:<4}{100*acc:>7.1f}%{age/3600:>7.1f}h"
              f"{rate:>8.2f}/min{eta/60:>8.1f}h{mark}")


if __name__ == "__main__":
    main()
