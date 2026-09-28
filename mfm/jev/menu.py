"""The bounded action menu: what JEV is allowed to choose from on this decision.

Upstream (`rmalde/minecraft-agent`) builds its candidate list fresh every loop iteration,
wraps each action in `bounded()` with a 25-second ceiling, and keeps a cooldown map: an
action that failed is dropped from the next list, and three consecutive failures null the
plan so the planner is called again. This module is that bookkeeping, with nothing of the
game in it -- the chassis builds the candidates (`mcu_worldmodel/jev.py`), this decides
which of them are still on offer and renders them as the endpoint's `criteria`.

The cooldown is counted in DECISIONS, not seconds: a tick is not a unit the model sees,
and an entry can spend anywhere from one tick to the step cap.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

#: The most options one question carries. JEV returns a probability per option, so the
#: menu is cheap to widen and expensive to make meaningless: 32 is about what the atom
#: set plus a handful of walked waypoints comes to.
MAX_OPTIONS = 32
#: Decisions an action sits out after failing, by how many times it has failed in a row.
COOLDOWN_STEPS = (3, 6, 12, 24)
#: Consecutive failures that drop the plan and call the planner (upstream: 3).
ERRORS_TO_REPLAN = 3
#: Always on the menu, as upstream's "wait: observe one tick when no useful action exists".
WAIT_KEY = "wait"


@dataclass(frozen=True)
class Candidate:
    """One bounded action, ready to enqueue if JEV picks it."""
    key: str                                    # the menu key JEV answers with
    entry: dict[str, Any]                       # {procedure, args} or {action, repeat}
    description: str                            # what choosing it means
    ticks: int = 0                              # what the parse says it will cost
    atom: str = ""                              # the procedure it is an instance of

    def criterion(self) -> str:
        cost = f" (~{self.ticks} ticks)" if self.ticks else ""
        return f"{self.description}{cost}"


@dataclass
class CandidateMenu:
    """Cooldowns, the consecutive-failure counter, and the filtered offer."""
    decisions: int = 0
    errors: int = 0
    #: key -> the decision index it becomes available again at.
    cooldown: dict[str, int] = field(default_factory=dict)
    #: key -> failures in a row (reset when it succeeds).
    fails: dict[str, int] = field(default_factory=dict)
    #: The last offer, by key, so a chosen key can be resolved back to its entry.
    offered: dict[str, Candidate] = field(default_factory=dict)
    max_options: int = MAX_OPTIONS

    # -- the offer ---------------------------------------------------------------------

    def offer(self, candidates: Iterable[Candidate], *, avoid: Iterable[str] = ()
              ) -> list[Candidate]:
        """The menu for this decision: cooled-down and planner-vetoed keys dropped,
        capped at `max_options`, `wait` always last and never dropped."""
        vetoed = {str(a).strip() for a in avoid if str(a).strip()}
        keep: list[Candidate] = []
        seen: set[str] = set()
        wait: Candidate | None = None
        for cand in candidates:
            if cand.key in seen:
                continue
            seen.add(cand.key)
            if cand.key == WAIT_KEY:
                wait = cand
                continue
            if self.cooldown.get(cand.key, -1) > self.decisions:
                continue
            # The planner vetoes by menu key or by the atom the key instantiates.
            if cand.key in vetoed or (cand.atom and cand.atom in vetoed):
                continue
            keep.append(cand)
        room = max(1, self.max_options - (1 if wait else 0))
        keep = keep[:room]
        if wait is not None:
            keep.append(wait)
        self.offered = {c.key: c for c in keep}
        return keep

    def criteria(self, menu: Iterable[Candidate] | None = None) -> dict[str, str]:
        """The endpoint's `criteria` object for a `choice` question."""
        return {c.key: c.criterion() for c in (menu if menu is not None
                                               else self.offered.values())}

    def resolve(self, key: Any) -> Candidate | None:
        """The candidate a returned choice names, or None if it named nothing offered."""
        return self.offered.get(str(key)) if key is not None else None

    # -- the outcome -------------------------------------------------------------------

    def note_decision(self) -> None:
        self.decisions += 1

    def note_success(self, key: str) -> None:
        self.fails.pop(key, None)
        self.cooldown.pop(key, None)
        self.errors = 0

    def note_failure(self, key: str) -> None:
        n = self.fails.get(key, 0) + 1
        self.fails[key] = n
        wait = COOLDOWN_STEPS[min(n, len(COOLDOWN_STEPS)) - 1]
        self.cooldown[key] = self.decisions + wait
        self.errors += 1

    @property
    def replan_due(self) -> bool:
        return self.errors >= ERRORS_TO_REPLAN

    def clear_errors(self) -> None:
        self.errors = 0

    def audit(self) -> dict[str, Any]:
        return {"decisions": self.decisions, "consecutive_errors": self.errors,
                "on_cooldown": sorted(k for k, until in self.cooldown.items()
                                      if until > self.decisions),
                "repeat_failures": {k: v for k, v in sorted(self.fails.items()) if v > 1},
                "max_options": self.max_options}
