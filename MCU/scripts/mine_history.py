#!/usr/bin/env python3
"""The history of a life's `mine/`: what the model had written by each step.

A life's record is indexed by step (logs.txt, index.jsonl, episodes/), so it can be cut
at any step afterwards. What the model writes for itself under `mine/` is edited in
place and keeps no history. This poller runs beside a life, never inside it: it reads
the workspace and writes only to its own directory, which the model cannot see.

    mine_history.py watch <memory dir> <history dir> [--every 20] [--idle 3600]
    mine_history.py at <history dir> <step>          # the manifest in force at <step>

    <history dir>/history.jsonl   one row per change: {"t", "step", "files": {path: sha1}}
    <history dir>/blobs/<sha1>    each distinct file content, once
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

_STEP = re.compile(rb"^Action \d+ \| Step (\d+)", re.M)


def current_step(memory: Path) -> int:
    """The step of the last action block in logs.txt (0 before the first)."""
    try:
        with open(memory / "logs.txt", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 262144))
            steps = _STEP.findall(f.read())
    except OSError:
        return 0
    return int(steps[-1]) if steps else 0


def manifest(mine: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not mine.is_dir():
        return out
    for p in sorted(mine.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            try:
                out[p.relative_to(mine).as_posix()] = p.read_bytes()
            except OSError:
                pass
    return out


def snapshot(memory: Path, history: Path, last: dict[str, str] | None) -> dict[str, str]:
    """Append a row if `mine/` differs from `last`; returns the manifest now in force."""
    step = current_step(memory)
    data = manifest(memory / "mine")
    files = {rel: hashlib.sha1(b).hexdigest() for rel, b in data.items()}
    if files == last:
        return files
    blobs = history / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    for rel, b in data.items():
        blob = blobs / files[rel]
        if not blob.exists():
            blob.write_bytes(b)
    with open(history / "history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "step": step,
                            "files": files}, sort_keys=True) + "\n")
    return files


def rows(history: Path) -> list[dict]:
    out = []
    for line in (history / "history.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def at(history: Path, step: int) -> dict | None:
    """The last row recorded at or before `step`: a file changed during the plan that
    ends past `step` is not in it."""
    best = None
    for r in rows(history):
        if r["step"] <= step:
            best = r
    return best


def watch(memory: Path, history: Path, every: float, idle: float) -> None:
    history.mkdir(parents=True, exist_ok=True)
    last: dict[str, str] | None = None
    if (history / "history.jsonl").exists():
        prior = rows(history)
        last = prior[-1]["files"] if prior else None
    seen_step, since = -1, time.time()
    while True:
        last = snapshot(memory, history, last)
        step = current_step(memory)
        if step != seen_step:
            seen_step, since = step, time.time()
        elif time.time() - since > idle:
            print(f"no new step for {idle:.0f}s at step {step}: the life is over", flush=True)
            return
        time.sleep(every)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("memory", type=Path)
    w.add_argument("history", type=Path)
    w.add_argument("--every", type=float, default=20.0)
    w.add_argument("--idle", type=float, default=3600.0)
    a = sub.add_parser("at")
    a.add_argument("history", type=Path)
    a.add_argument("step", type=int)
    args = ap.parse_args()
    if args.cmd == "watch":
        watch(args.memory, args.history, args.every, args.idle)
    else:
        row = at(args.history, args.step)
        json.dump(row, sys.stdout, indent=1, sort_keys=True)
        print()


if __name__ == "__main__":
    main()
