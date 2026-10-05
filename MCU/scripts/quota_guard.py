#!/usr/bin/env python3
"""Stop a SLURM job before its Claude arms run past the subscription they spend.

A subscription arm past its limit does not fail. Every turn is answered with a 429
("You've hit your weekly limit"), the harness plays the refused turn as a no-op, and the
life runs on to its last step with nothing behind it: two probe lives on 2026-10-04 played
1,424 refused turns that way. The CLI writes the account's windows into every turn's event
stream (`rate_limit_event`: a status, and the 5-hour and 7-day utilization), so the state
is on disk seconds after each turn. This reads the newest one and cancels the job when

  * a turn was refused (status `rejected`) -- always, on any account; or
  * a window is at or past its cap (--cap-5h, --cap-7d; off above 1.0) -- for an account
    that somebody also works on, where the rest of the window is theirs.

It only ever stops the job. Nothing the agent sees or does depends on it. The life it cut
has no result file, so the launcher runs it again from scratch and never uses it as the
source of a later life.

    python3 scripts/quota_guard.py --job $SLURM_JOB_ID --root output --prefix sr3l \
        --cap-5h 0.80 --cap-7d 0.75 --marker logs/quota_stop-$SLURM_JOB_ID.json &
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

OFF = 1.01   # a cap above 1.0 never trips: only a refused turn stops the job


def last_event(path: str) -> dict | None:
    """The last rate-limit record of one turn's event stream, or None."""
    info = None
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                if '"rate_limit_event"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev.get("rate_limit_info"), dict):
                    info = ev["rate_limit_info"]
    except OSError:
        return None
    return info


def newest_event(root: str, prefix: str, since: float) -> tuple[str, dict] | None:
    """The newest rate-limit record written since `since` by any life under root/prefix*."""
    pattern = os.path.join(root, prefix + "*", "episode_*", "codex_turns", "turn_*.events.jsonl")
    stamped = []
    for path in glob.glob(pattern):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime >= since:
            stamped.append((mtime, path))
    for _, path in sorted(stamped, reverse=True):
        info = last_event(path)
        if info is not None:
            return path, info
    return None


def windows(info: dict) -> dict:
    """{'five_hour': utilization, 'seven_day': utilization} as far as the record says."""
    out = {}
    for name, win in (info.get("unifiedWindows") or {}).items():
        if isinstance(win, dict) and isinstance(win.get("utilization"), (int, float)):
            out[name] = float(win["utilization"])
    kind = info.get("rateLimitType")
    if kind and kind not in out and isinstance(info.get("utilization"), (int, float)):
        out[kind] = float(info["utilization"])
    return out


def verdict(info: dict, cap_5h: float = OFF, cap_7d: float = OFF) -> str | None:
    """Why the job has to stop, or None while it may run."""
    if info.get("status") == "rejected":
        return "a turn was refused (%s limit reached)" % (info.get("rateLimitType") or "a")
    used = windows(info)
    if used.get("five_hour", 0.0) >= cap_5h:
        return "the 5-hour window is at %.0f%%, cap %.0f%%" % (100 * used["five_hour"], 100 * cap_5h)
    if used.get("seven_day", 0.0) >= cap_7d:
        return "the 7-day window is at %.0f%%, cap %.0f%%" % (100 * used["seven_day"], 100 * cap_7d)
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", default=os.environ.get("SLURM_JOB_ID", ""), help="the job to cancel")
    ap.add_argument("--root", default="output")
    ap.add_argument("--prefix", default="", help="arm-name prefix of the lives to watch")
    ap.add_argument("--cap-5h", type=float, default=OFF)
    ap.add_argument("--cap-7d", type=float, default=OFF)
    ap.add_argument("--every", type=float, default=20.0, help="seconds between looks")
    ap.add_argument("--since", type=float, default=None, help="epoch; default: now")
    ap.add_argument("--marker", default="", help="file that records why the job was stopped")
    ap.add_argument("--once", action="store_true", help="look once: exit 3 on a stop verdict")
    ap.add_argument("--dry-run", action="store_true", help="never scancel")
    args = ap.parse_args(argv)
    since = time.time() if args.since is None else args.since

    seen = None
    while True:
        found = newest_event(args.root, args.prefix, since)
        if found is not None:
            path, info = found
            why = verdict(info, args.cap_5h, args.cap_7d)
            used = windows(info)
            state = (info.get("status"), used.get("five_hour"), used.get("seven_day"))
            if state != seen:   # one line per change, so the job log shows the draw
                print("--- quota guard: status %s, 5-hour %s, 7-day %s (%s)"
                      % (state + (os.path.relpath(path, args.root),)), flush=True)
                seen = state
            if why:
                record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "job": args.job, "why": why,
                          "file": path, "status": info.get("status"), "windows": used,
                          "resetsAt": info.get("resetsAt")}
                print("=== QUOTA STOP: %s -- cancelling job %s" % (why, args.job or "(none)"), flush=True)
                if args.marker:
                    with open(args.marker, "w") as fh:
                        json.dump(record, fh)
                        fh.write("\n")
                if args.job and not args.dry_run and not args.once:
                    subprocess.call(["scancel", str(args.job)])
                return 3
        if args.once:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
