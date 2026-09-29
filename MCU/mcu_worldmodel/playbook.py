"""Branch a run from a previous trajectory: replay its entries, then go live.

The fix-iteration loop was paying full price for its prefixes: testing a descent
change meant re-running 6000 steps of already-solved early game at one model call
per turn, ~2 hours to reach the part under test. But the world is deterministic
(seed 0, fixed spawn) and `logs.txt` records every entry the previous run executed
-- so the prefix can be replayed at the PROCEDURE level: the same closed-loop
entries (chop re-aims, dig re-verifies, goto re-navigates) re-solve the segment
like a walkthrough, robust to small divergence, at pure sim speed with zero model
calls. When the playbook runs dry, the real backend takes over mid-episode with
logs.txt showing one coherent history.

This is Go-Explore's "first return, then explore" as debugging infrastructure:
return deterministically to the frontier, spend the model only on the frontier.

Discipline: a branched run is a DIAGNOSTIC, never a scoreboard entry. Its prefix
is the old policy's choices; its milestones re-fire honestly during replay, but
the score is not comparable to a from-scratch run and must not be reported as one.
"""
from __future__ import annotations

import ast
import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Callable

_HEADER = re.compile(r"^Action (\d+) \| Step (\d+)(?: \| Plan Step (\d+)/(\d+))?")
_MILESTONE = re.compile(r"MILESTONE \S+ verified")
_PROC = re.compile(r"^\[ACTION\] ([A-Za-z_][A-Za-z_0-9]*)\((.*)\) -> \d+ ticks")
_RAW = re.compile(r"^\[ACTION\] (\{.*\}) x(\d+)")


def _split_args(argstr: str) -> list[str]:
    """Split on the commas BETWEEN arguments, not the ones inside a value.

    `stow_items(grid=2x2,cells=[0,1])` is one entry with two arguments; a plain
    `split(",")` makes three, and the replay executed `cells='[0'` -- measured in rp02
    (2026-09-03), where every stow in the prefix reported `stow_items: bad cell '[1'`
    and moved nothing.
    """
    parts, depth, cur = [], 0, []
    for ch in argstr:
        if ch in "[({":
            depth += 1
        elif ch in "])}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return parts


def _parse_args(argstr: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for part in _split_args(argstr):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k:
            continue
        try:
            out[k] = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            out[k] = v
    return out


def extract_milestone_schedule(logs_txt: Path) -> list[tuple[int, int]]:
    """(step, cumulative milestone count) each time the source run banked one.

    The replay's divergence check reads this: if the live run has fewer milestones
    than the source had by (live_step - grace), the world has forked from the
    recording and replaying further is walking someone else's route in the wrong
    world -- hand over early instead."""
    out: list[tuple[int, int]] = []
    step = 0
    count = 0
    for line in Path(logs_txt).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _HEADER.match(line)
        if m:
            step = int(m.group(2))
            continue
        if _MILESTONE.search(line):
            count += 1
            out.append((step, count))
    return out


def extract_playbook(logs_txt: Path, until_step: int) -> list[dict[str, Any]]:
    """Entry sequence from a previous run's log, grouped back into its turns.

    `Plan Step i/k` is written per executed entry; i==1 (or i folding back) marks a
    turn boundary. Entries after `until_step` are dropped, and so is anything that
    is not an [ACTION] line -- initial state, induction summaries, notes.
    """
    turns: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    prev_i = 0
    step = None
    plan_i = None
    for line in Path(logs_txt).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _HEADER.match(line)
        if m:
            step = int(m.group(2))
            plan_i = int(m.group(3)) if m.group(3) else None
            continue
        if step is None or step > until_step:
            continue
        entry: dict[str, Any] | None = None
        m = _PROC.match(line)
        if m:
            entry = {"procedure": m.group(1), "args": _parse_args(m.group(2))}
        else:
            m = _RAW.match(line)
            if m:
                try:
                    entry = {"action": json.loads(m.group(1)),
                             "repeat": int(m.group(2))}
                except json.JSONDecodeError:
                    entry = None
        if entry is None:
            continue
        i = plan_i if plan_i is not None else 1
        if cur and i <= prev_i:
            turns.append(cur)
            cur = []
        cur.append(entry)
        prev_i = i if plan_i is not None else 0
    if cur:
        turns.append(cur)
    return [{"actions": t} for t in turns]


class PlaybookCodex:
    """Shadow backend: serves recorded turns for free, then steps aside.

    Wraps the real backend and answers act turns from the playbook until it is
    exhausted; every later call passes straight through. `on_exhausted` fires
    once at the handover -- the executor uses it to re-enable induction, which
    is suppressed during replay because a replayed prefix has nothing to induce
    that the seeded memory does not already carry.
    """

    def __init__(self, real: Any, turns: list[dict[str, Any]],
                 on_exhausted: Callable[[], None] | None = None,
                 schedule: list[tuple[int, int]] | None = None,
                 progress: Callable[[], tuple[int, int]] | None = None,
                 grace_steps: int = 800) -> None:
        self._real = real
        self._turns = deque(turns)
        self._on_exhausted = on_exhausted
        self._schedule = list(schedule or [])
        self._progress = progress
        self._grace = int(grace_steps)
        self.replaying = bool(turns)
        self.replayed = 0
        self.aborted_at: int | None = None

    def _diverged(self) -> bool:
        if not (self._schedule and self._progress):
            return False
        step, have = self._progress()
        due = sum(1 for s, _ in self._schedule if s <= step - self._grace)
        return have < due

    def write_system_prompt(self, text: str) -> None:
        self._real.write_system_prompt(text)

    def run(self, prompt: str, images=(), *, expect_actions: bool = True) -> dict:
        if self._turns and self._diverged():
            step, have = self._progress()
            self.aborted_at = step
            self._turns.clear()
        if self._turns:
            turn = self._turns.popleft()
            self.replayed += 1
            return {"actions_json": json.dumps(turn), "ok": True,
                    "message": f"[PLAN]\nplaybook replay {self.replayed}",
                    "error": None, "overflow": False}
        if self.replaying:
            self.replaying = False
            if self._on_exhausted:
                self._on_exhausted()
        return self._real.run(prompt, images, expect_actions=expect_actions)

    def read_outputs(self) -> dict:
        if self.replaying:
            return {"hypotheses_ops": None, "claim": None, "errors": []}
        return self._real.read_outputs()

    def split_briefing(self, message: str):
        return self._real.split_briefing(message)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)
