#!/usr/bin/env python3
"""Audit what an arm's model actually ran: every shell command in its codex turn
events, flagged when it reaches outside the workspace.

Codex's workspace-write sandbox is not enforced on this host (kernel 5.11 has no
landlock, which arrived in 5.13): a probe run through `codex exec` with the arms'
flags wrote both /tmp/<file> and ../<file>. So "only logs.txt persists" for the
logbook arm rests on the turn-end sweep of ./ plus this audit of the transcript, not
on the sandbox. Run it on every landed logbook arm; any OUTSIDE line is a finding.

    scripts/audit_turn_commands.py kdc1z_logbook_high [more arms...]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

OUTSIDE = re.compile(r"/tmp|TMPDIR|~/|\$HOME|/var/|/datapool|/home|\.\./|/proc\b|/dev/(?!null)|\bcd\b|\bpwd\b|find /|realpath")


def shell_text(command: str) -> str:
    m = re.search(r"-lc [\"'](.*)", command, re.S)
    return (m.group(1) if m else command).strip()


def audit(arm: str) -> int:
    turns = Path("output") / arm / "episode_001" / "codex_turns"
    files = sorted(turns.glob("turn_*.events.jsonl"))
    heads: Counter = Counter()
    outside: list[tuple[str, str, object]] = []
    n_cmd = 0
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "item.completed":
                continue
            it = e.get("item", {})
            if it.get("type") != "command_execution":
                continue
            n_cmd += 1
            s = shell_text(it.get("command", ""))
            heads[s.split()[0] if s else "?"] += 1
            if OUTSIDE.search(s):
                outside.append((f.name, s[:160], it.get("exit_code")))
    print(f"{arm}: {len(files)} turns, {n_cmd} shell commands, "
          f"by first word {dict(heads.most_common(8))}")
    for name, s, code in outside:
        print(f"  OUTSIDE {name} exit={code} :: {s}")
    print(f"  outside-reaching commands: {len(outside)}")
    return len(outside)


if __name__ == "__main__":
    arms = sys.argv[1:] or sys.exit(__doc__)
    sys.exit(1 if sum(audit(a) for a in arms) else 0)
