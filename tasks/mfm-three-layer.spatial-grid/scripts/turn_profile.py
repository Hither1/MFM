#!/usr/bin/env python3
"""Per-turn behaviour profile of an arm: what the model spends its turns on.

    python turn_profile.py <MCU dir> <arm> [--first N] [--last N]

Reads output/<arm>/episode_001/codex_turns/turn_*.events.jsonl (commands, usage),
memory/logs.txt (plan entries, steps), logs/<arm>_purple.log (turn and milestone
times) and memory/mine/ (digest/working sizes). Written 2026-09-09 to compare gen 3
(of3g) with gen 2 (of3r) and to read out the gen-3b smoke; the kinds match
analysis/gen3_vs_gen2_2026-09-09.md.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics as st
from pathlib import Path

KINDS = [
    ("read_skill", r"skills/\w+/SKILL\.md|\.agents/skills"),
    ("read_ref", r"references/"),
    ("query", r"episodes\.py"),
    ("look", r"view_image|zoom\.py|then-now"),
    ("read_prev", r"previous/"),
    ("validate", r"json\.tool"),
    ("read_log", r"logs\.txt"),
]
WRITE = re.compile(r"apply_patch|cat >|python - <<|tee ")
WRITE_TARGETS = ["working.md", "digest.md", "notes.md", "actions.json", "reflexes/",
                 "procedures/", "skills/"]


def kinds_of(cmd: str) -> list[str]:
    out = [k for k, pat in KINDS if re.search(pat, cmd)]
    if WRITE.search(cmd):
        t = [w.rstrip("/").split(".")[0] for w in WRITE_TARGETS if w in cmd]
        out.append("write:" + "+".join(t) if t else "write:other")
    return out or ["other"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mcu")
    ap.add_argument("arm")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, default=0)
    a = ap.parse_args()
    mcu = Path(a.mcu)
    ep = mcu / "output" / a.arm / "episode_001"
    files = sorted(glob.glob(str(ep / "codex_turns" / "turn_*.events.jsonl")))
    if a.first:
        files = files[:a.first]
    if a.last:
        files = files[-a.last:]
    cats: dict[str, int] = {}
    cmds = msgs = 0
    outs: list[int] = []
    for f in files:
        ev = [json.loads(l) for l in open(f) if l.strip()]
        for e in ev:
            if e.get("type") != "item.completed":
                continue
            it = e["item"]
            if it.get("type") == "command_execution":
                cmds += 1
                for k in kinds_of(it.get("command", "")):
                    cats[k] = cats.get(k, 0) + 1
            elif it.get("type") == "agent_message":
                msgs += len(it.get("text", ""))
        u = [e.get("usage") for e in ev if e.get("type") == "turn.completed"]
        if u and u[0]:
            outs.append(int(u[0].get("output_tokens", 0)))
    n = len(files) or 1
    deltas = [b - x for x, b in zip(outs, outs[1:]) if b >= x]
    print(f"== {a.arm}: {len(files)} turns, {cmds / n:.2f} cells/turn, {msgs / n:.0f} msg chars/turn, "
          f"output tokens/turn median {st.median(deltas) if deltas else 'n/a'}")
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"   {k:32s} {v:4d}  {v / n:.2f}/turn")
    # plan grain and pace
    log = ep / "memory" / "logs.txt"
    if log.exists():
        steps = [int(m.group(1)) for m in re.finditer(r"^Action \d+ \| Step (\d+)", log.read_text(errors="replace"), re.M)]
        d = [b - x for x, b in zip(steps, steps[1:])]
        if d:
            print(f"   plan entries {len(steps)}, steps/entry median {st.median(d)}, mean {st.mean(d):.1f}, last step {steps[-1]}")
    purple = mcu / "logs" / f"{a.arm}_purple.log"
    if purple.exists():
        text = purple.read_text(errors="replace")
        turns = len(re.findall(r"\[codex\] turn \d+ model", text))
        last_step = re.findall(r"step (\d+)", text)
        ms = re.findall(r"\[milestone\] (\w+) at step (\d+) \((\d+)/24\)", text)
        if turns and last_step:
            print(f"   purple: {turns} turns, last step {last_step[-1]}, {int(last_step[-1]) / turns:.0f} steps/turn; "
                  f"milestones {len(ms)}" + (f", last {ms[-1][0]} @{ms[-1][1]}" if ms else ""))
        ts = re.findall(r"^(\S+ \S+) \| INFO .*\[codex\] turn \d+ model", text, re.M)
        if len(ts) > 2:
            import datetime as dt
            t = [dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f") for x in ts]
            gaps = [(b - x).total_seconds() for x, b in zip(t, t[1:])]
            print(f"   turn interval median {st.median(gaps):.0f} s (mean {st.mean(gaps):.0f})")
    mine = ep / "memory" / "mine"
    for name in ("digest.md", "working.md", "notes.md"):
        p = mine / name
        if p.exists():
            t = p.read_text(errors="replace")
            print(f"   {name}: {len(t.encode())} B, {t.count(chr(10)) + 1} lines")
    for d in ("procedures", "reflexes", "skills"):
        p = mine / d
        print(f"   mine/{d}: {sorted(os.listdir(p)) if p.is_dir() else []}")
    contract = ep / "memory" / "AGENTS.md"
    if contract.exists():
        c = contract.read_text(errors="replace")
        print(f"   contract {len(c.encode())} B; thread-persists sentence: {'Your thread persists' in c}; "
              f"'does not persist': {'does not persist' in c}; pace rule: {'A plan runs open-loop' in c}")


if __name__ == "__main__":
    main()
