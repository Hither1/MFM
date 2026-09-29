"""The layer above the plan: what the agent is currently trying to do, and what it costs.

PRO-LONG has exactly two levels of control -- the action and the plan -- and the only
thing that can interrupt a plan in flight is the environment's own task-verification bit
(`ProlongAgent.get_action`'s queue flush). Nothing interrupts a *sequence* of plans that
keeps re-committing to the same subgoal, and the full-log re-read makes that worse rather
than better: `logs.txt` carries the agent's own prior `[PLAN]` blocks, so a subgoal
adopted reflexively at one step is re-justified on every later turn by the hundred turns
that already pursued it. In the dragon run this cost 5,887 steps -- 52% of the episode,
132 planning turns, 89 steps per block -- climbing from y=5 back to y=71 because a fall
had been classified as something to recover from, in the exact depth band where the
task's iron and diamond are. Every individual turn was locally correct; no turn asked
why it was climbing.

This module is the missing level, and it is deliberately small:

  * the analyzer names its current subgoal in `actions.json` (`"subgoal"`),
  * the runner meters what that subgoal has cost in steps and in *measured* progress,
    taken from the simulator rather than from the agent's own account of itself,
  * when the cost passes a budget, `review_due` goes true and the next plan is invalid
    until the agent either names a different subgoal or justifies keeping this one.

The forcing is the whole point. A note the agent may read and skip is what it already
has -- `[NOTE]` -- and a subgoal that survived 131 self-confirmations will survive a
132nd suggestion. `reject_reason` makes the turn fail closed instead.

Similarity, not equality, decides whether a subgoal is "the same": rewording "climb back
to the surface" as "climb back up to the surface" must not reset the meter, or the budget
measures the agent's vocabulary instead of its commitment. Token overlap cannot catch a
true synonym ("ascend to daylight"), so it is not the only trigger: a second meter runs on
the environment's own verified milestones and is blind to what the subgoal is called. The
dragon run's 5,887-step climb scored nothing for its whole duration, which is the fact
that most deserved to interrupt it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from prolong_mc.log import _inventory_counts

_WORD_RE = re.compile(r"[a-z0-9]+")
# Only closed-class words. "back", "up", "down" and "out" carry the direction of a
# recovery subgoal and are exactly what distinguishes it from its opposite.
_STOP = {
    "the", "a", "an", "to", "and", "of", "for", "with", "in", "on", "at", "then",
    "i", "my", "it", "is", "this", "that", "so", "as", "by", "or",
}
_SAME_SUBGOAL = 0.6


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP}


def _same_subgoal(a: str, b: str) -> bool:
    """Jaccard over content words. Identical strings are the common case; the overlap
    test is there for the paraphrase that would otherwise re-arm the budget for free."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return (a or "").strip().lower() == (b or "").strip().lower()
    return len(wa & wb) / len(wa | wb) >= _SAME_SUBGOAL


def _y(pos: Any) -> float | None:
    if not isinstance(pos, dict):
        return None
    try:
        return float(pos.get("y"))
    except (TypeError, ValueError):
        return None


def _flat_dist(a: Any, b: Any) -> float | None:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    try:
        return math.dist((float(a["x"]), float(a["z"])), (float(b["x"]), float(b["z"])))
    except (KeyError, TypeError, ValueError):
        return None


@dataclass
class _Span:
    """One contiguous commitment to a subgoal."""
    subgoal: str
    start_step: int
    start_pos: dict | None
    start_inv: dict[str, int]
    review_at: int
    turns: int = 1
    recommits: int = 0
    steps: int = 0
    last_pos: dict | None = None
    last_inv: dict[str, int] = field(default_factory=dict)


class GoalTracker:
    """Meters the current subgoal and decides when it has to be re-derived.

    `budget_steps` is the interval, not a one-shot: a justified re-commitment buys
    another `budget_steps` and is then asked again, with the cumulative cost. That is
    what stops a single "yes, keep climbing" from licensing the remaining 5,000 steps.
    """

    def __init__(self, budget_steps: int, task_text: str = "",
                 stall_multiple: int = 3) -> None:
        self.budget_steps = int(budget_steps)
        # The milestone meter is deliberately slacker than the subgoal meter: a subgoal
        # is supposed to be finished and replaced often, whereas a stretch with no
        # verified milestone is normal early in a tech tree. It is the backstop, not the
        # primary trigger.
        self.stall_budget = int(budget_steps) * int(stall_multiple)
        self.task_text = (task_text or "").strip()
        self.span: _Span | None = None
        self.reviews = 0
        self.rejections = 0
        self.abandonments = 0
        self.recommits = 0
        self.stall_reviews = 0
        self.unanswered = 0
        self._episode_steps = 0
        self._history: list[tuple[str, int, int]] = []  # (subgoal, steps, turns)
        self._milestones_done = 0
        self._stall_since = 0
        self._stall_review_at = self.stall_budget

    # -- metering --------------------------------------------------------

    def observe_step(self, step: int, info: dict | None) -> None:
        """Called once per environment tick, with the state that tick produced."""
        self._episode_steps = max(self._episode_steps, int(step))
        # The environment's own verification, which no rewording of a subgoal can move.
        spec = (info or {}).get("milestone_spec")
        if isinstance(spec, list) and spec:
            done = sum(1 for m in spec if isinstance(m, dict) and m.get("done"))
            if done > self._milestones_done:
                self._milestones_done = done
                self._stall_since = int(step)
                self._stall_review_at = self.stall_budget
        if self.span is None:
            return
        self.span.steps = max(self.span.steps, int(step) - self.span.start_step)
        info = info or {}
        pos = info.get("player_pos")
        if isinstance(pos, dict):
            self.span.last_pos = pos
        inv = _inventory_counts(info)
        if inv or "inventory" in info:
            self.span.last_inv = inv

    @property
    def stall_steps(self) -> int:
        return max(0, self._episode_steps - self._stall_since)

    @property
    def review_due(self) -> bool:
        return bool(self._triggers())

    def _triggers(self) -> list[str]:
        """Which meters have tripped. Both can be true at once, and the review says so."""
        out = []
        if self.span is not None and self.span.steps >= self.span.review_at:
            out.append("subgoal")
        if self.span is not None and self.stall_steps >= self._stall_review_at:
            out.append("stall")
        return out

    @property
    def current(self) -> str:
        return self.span.subgoal if self.span else ""

    # -- the contract ----------------------------------------------------

    def note_rejection(self) -> None:
        """Called by the runner when it actually rejects a plan. `reject_reason` is
        pure: it is asked on the final attempt too, where the answer is reported but
        the plan is accepted anyway, and counting there overstated rejections by the
        retry factor."""
        self.rejections += 1

    def reject_reason(self, subgoal: str, recommit: str) -> str | None:
        """Why this plan cannot be accepted, or None if it can.

        Only ever fires on a review turn. Re-committing is allowed -- sometimes the
        subgoal really is right -- but it has to be said, in the `recommit` field, in
        the same breath as the cost the runner just showed.
        """
        if not self.review_due:
            return None
        subgoal = (subgoal or "").strip()
        if not subgoal:
            return (
                "Your actions.json has no `subgoal` field. This is a review turn: name "
                "the subgoal these actions serve."
            )
        if not _same_subgoal(subgoal, self.current):
            return None
        if (recommit or "").strip():
            return None
        return (
            f"This is a review turn and you re-submitted the same subgoal "
            f"({self.current!r}) after {self.span.steps} steps on it. Either name a "
            f"different subgoal, or keep this one by adding a top-level "
            f'`"recommit": "<one sentence: why this subgoal still beats every '
            f'alternative for the task, and what it will cost from here>"` to '
            f"actions.json. Answer the accounting above; do not restate the plan."
        )

    def adopt(self, subgoal: str, recommit: str, step: int, info: dict | None) -> None:
        """Record the subgoal a just-accepted plan serves."""
        subgoal = (subgoal or "").strip() or "(unnamed)"
        info = info or {}
        triggers = self._triggers()
        if self.span is not None and _same_subgoal(subgoal, self.span.subgoal):
            self.span.turns += 1
            if triggers:
                # Re-armed from where they stand, so the next review lands one budget
                # later and reports the cumulative cost, not a fresh zero. The counters
                # only move for a *stated* re-commitment: a review the runner gave up on
                # and accepted anyway is a different event, and conflating the two would
                # make an unanswered review look like a considered one in the audit.
                if (recommit or "").strip():
                    self.span.recommits += 1
                    self.recommits += 1
                else:
                    self.unanswered += 1
                self.span.review_at = self.span.steps + self.budget_steps
                if "stall" in triggers:
                    self._stall_review_at = self.stall_steps + self.stall_budget
            return
        if self.span is not None:
            if triggers:
                self.abandonments += 1
                # A different subgoal answers the subgoal meter, but not the milestone
                # one -- renaming the commitment is exactly what that meter is for.
                if "stall" in triggers:
                    self._stall_review_at = self.stall_steps + self.stall_budget
            self._history.append((self.span.subgoal, self.span.steps, self.span.turns))
        pos = info.get("player_pos") if isinstance(info.get("player_pos"), dict) else None
        inv = _inventory_counts(info)
        self.span = _Span(
            subgoal=subgoal,
            start_step=int(step),
            start_pos=pos,
            start_inv=inv,
            review_at=self.budget_steps,
            last_pos=pos,
            last_inv=inv,
        )

    # -- what the review turn is told ------------------------------------

    def _accounting(self) -> list[str]:
        span = self.span
        assert span is not None
        share = (100.0 * span.steps / self._episode_steps) if self._episode_steps else 0.0
        lines = [
            f"  subgoal: {span.subgoal!r}",
            f"  cost so far: {span.steps} environment steps over {span.turns} planning "
            f"turns ({share:.0f}% of the {self._episode_steps} steps this episode has used)",
        ]
        if span.recommits:
            lines.append(
                f"  you have already re-committed to this subgoal {span.recommits}x"
            )
        y0, y1 = _y(span.start_pos), _y(span.last_pos)
        if y0 is not None and y1 is not None:
            per = (span.steps / abs(y1 - y0)) if abs(y1 - y0) >= 1.0 else None
            rate = f" ({per:.0f} steps per block of y)" if per else ""
            lines.append(f"  y: {y0:.1f} -> {y1:.1f} (net {y1 - y0:+.1f}){rate}")
        flat = _flat_dist(span.start_pos, span.last_pos)
        if flat is not None:
            lines.append(
                f"  horizontal displacement from where this subgoal started: {flat:.1f} blocks"
            )
        gained = {k: v - span.start_inv.get(k, 0) for k, v in span.last_inv.items()
                  if v > span.start_inv.get(k, 0)}
        lost = {k: span.start_inv[k] - span.last_inv.get(k, 0) for k in span.start_inv
                if span.start_inv[k] > span.last_inv.get(k, 0)}
        if gained or lost:
            parts = [f"+{v} {k}" for k, v in sorted(gained.items())]
            parts += [f"-{v} {k}" for k, v in sorted(lost.items())]
            lines.append(f"  inventory change under this subgoal: {', '.join(parts)}")
        else:
            lines.append("  inventory change under this subgoal: none")
        lines.append(
            f"  environment-verified milestones: {self._milestones_done}; "
            f"steps since the last one was verified: {self.stall_steps}"
        )
        if self._history:
            past = "; ".join(f"{g!r} {s} steps/{t} turns" for g, s, t in self._history[-4:])
            lines.append(f"  earlier subgoals this episode: {past}")
        return lines

    def review_prompt(self) -> str:
        """Prepended to the turn prompt when the budget trips. Deliberately not phrased
        as advice: the numbers are the runner's, and the question is not rhetorical."""
        triggers = self._triggers()
        self.reviews += 1
        if "stall" in triggers:
            self.stall_reviews += 1
        body = "\n".join(self._accounting())
        task = f"\nThe task is: {self.task_text}\n" if self.task_text else ""
        why = {
            ("subgoal",): (
                f"this subgoal has now cost more than {self.budget_steps} steps"),
            ("stall",): (
                f"the environment has verified no new milestone in "
                f"{self.stall_steps} steps, across every subgoal you have named in "
                f"that window"),
        }.get(tuple(triggers), (
            f"this subgoal has cost more than {self.budget_steps} steps AND the "
            f"environment has verified no new milestone in {self.stall_steps} steps"))
        return (
            "=== SUBGOAL REVIEW (required this turn) ===\n"
            f"Triggered because {why}.\n"
            "The runner is metering what you are currently doing. Measured, not "
            "reported by you:\n\n"
            f"{body}\n"
            f"{task}\n"
            "Before you plan anything, answer these three questions in your briefing, "
            "in order:\n"
            "  1. What made you adopt this subgoal? Find the turn where it started "
            "(grep the log for the earliest [PLAN] that mentions it) and say what the "
            "state was then. Your later plans agreeing with it is not evidence -- they "
            "were written by you, after the decision.\n"
            "  2. Is the reason still true, and is finishing this subgoal still the "
            "cheapest way to advance the TASK from where you are NOW? Compare it "
            "against at least one concrete alternative available at your current "
            "position and inventory.\n"
            "  3. If yes, what does it cost from here, and what would tell you it has "
            "failed?\n\n"
            "Then either name a different `subgoal` in actions.json, or keep this one "
            'by adding a top-level `"recommit": "<your answer to 2 and 3, one '
            'sentence>"`. A plan that repeats this subgoal without `recommit` is '
            "rejected.\n"
            "=== END SUBGOAL REVIEW ===\n\n"
        )

    def review_note(self) -> str:
        """The same event, one line, for the append-only record."""
        span = self.span
        assert span is not None
        return (
            f"REVIEW: subgoal {span.subgoal!r} reached {span.steps} steps over "
            f"{span.turns} planning turns with no verified milestone in "
            f"{self.stall_steps} steps; the runner required it to be re-derived or "
            f"replaced before the next plan was accepted."
        )

    def audit(self) -> dict[str, Any]:
        spans = list(self._history)
        if self.span is not None:
            spans.append((self.span.subgoal, self.span.steps, self.span.turns))
        return {
            "goal_budget_steps": self.budget_steps,
            "milestone_stall_budget_steps": self.stall_budget,
            "subgoal_reviews": self.reviews,
            "subgoal_reviews_from_milestone_stall": self.stall_reviews,
            "subgoal_rejections": self.rejections,
            "subgoal_recommits": self.recommits,
            "subgoal_reviews_unanswered": self.unanswered,
            "subgoal_abandonments": self.abandonments,
            "subgoals": [{"subgoal": g, "steps": s, "turns": t} for g, s, t in spans],
            "longest_subgoal_steps": max((s for _, s, _ in spans), default=0),
        }
