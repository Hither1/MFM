"""Null-entry governor: the cross-turn counterpart of the tick guards.

The tick guards (dig/stair no-descent stops, zero-break stops) close waste INSIDE one
program. What they cannot see is the waste BETWEEN programs: an entry that runs to a
clean finish and changes nothing, re-proposed turn after turn by a model whose session
was discarded and who is seeing the situation for the first time, every time. Measured
across ten 12k-step runs, 23-36% of the budget sat in >=300-step stretches of exactly
that (records: 11-19%) -- orientation preambles, hotbar churn, GUI fiddling, re-aims.

The literature is unambiguous about where the fix lives. A frozen LLM asked to notice
its own loop has published negative evidence (XENON: algorithmic memory revision 0.60
vs 0.40 for self-correction; RedundancyBench: LLM judges catch ~25% of redundant
steps). So the harness holds the memory and enforces: count zero-outcome entries per
(procedure, place), NUDGE on the second, refuse the third BEFORE it spends steps --
Glover's tabu list (1989) with its two classical safety valves, aspiration (a ban
lifts when the world moves: new item type, new milestone) and tenure (bans expire).

A refusal costs one model turn and zero sim steps; the entry it blocks costs 40-400
sim steps and, on the evidence above, returns nothing.
"""
from __future__ import annotations

from collections import deque
from typing import Any

# An entry is NULL when it produced no event line (mine/craft/pickup/milestone all
# arrive through _pending_events), moved the agent less than these, and changed no
# inventory count. The displacement floor is generous: turning in place, stepping to
# a shaft centre, nudging against a wall all stay under it; an entry that actually
# went somewhere clears it.
NULL_MOVE_EPS = 2.0
NULL_DESCENT_EPS = 1.5

NUDGE_AT = 2        # second consecutive null at the same key -> note in the prompt
VETO_AT = 3         # third proposal of the key while banned -> refused, zero steps
TENURE_STEPS = 1500  # a ban this old is stale terrain knowledge, not discipline
WINDOW_STEPS = 500   # the ledger line's lookback

# Only verbatim-churn procedures can arm a veto. Everything else is nudged but never
# refused: travel changes the key by design; the descents carry their own tick
# guards; GUI and cursor micro-ops legitimately produce "no inventory change" one
# entry at a time inside a craft sequence (one run: banning them broke the recovery
# of a dropped crafting table and burned 40 model calls at 2 per sim step); raw
# entries include furnace waits. The veto itself is ALL-OR-NOTHING per plan -- see
# Governor.check's caller -- because dropping one entry out of a composite plan
# (the aim before a mine) corrupts the plan instead of saving its steps.
VETOABLE = {"look", "look_abs", "look_at", "aim_at_tree", "aim_at_ore",
            "equip_hotbar", "chop_tree", "mine_ahead", "mine_forward",
            "strip_mine", "collect_drops"}

# The plan-level watchdog. The per-label rule above never fired on the loops that
# ate the chain: one run's furnace loop was equip_hotbar / close_inventory /
# craft / use_until_gui -- four labels, none vetoable, rotated turn after turn at
# one spot for ~10k steps; historically 58% of the null actions were GUI micro-ops
# and 13% raw holds. So a second ledger counts null entries per 8-block cell
# regardless of label, and a plan proposed from a stalled cell must contain a
# MOVE or an OPEN (a screen is where the null GUI work becomes productive), or it
# is dropped for one no-op with a note that says where the map suggests going.
CELL_STREAK_VETO = 4     # consecutive null entries at a cell, any labels
STALL_STEPS = 600        # or this long without a productive entry at the cell
SWITCH_STEPS = 1200      # ...and past this the note says to change the objective
MOVERS = frozenset({
    "go_to", "travel", "travel_bearing", "mine_forward", "strip_mine", "stair_down",
    "dig_down", "dig_up", "pillar_up", "bridge_forward", "walk", "explore",
    "explore_nether", "find_lava", "fetch_water", "swim_up", "climb", "descend",
    "tunnel", "run", "harvest_tree", "enter_portal", "enter_end",
})
OPENERS = frozenset({"use_until_gui", "open_inventory", "place_and_open"})
_MOVE_KEYS = ("forward", "back", "left", "right")


def entry_moves(entry: dict[str, Any]) -> bool:
    if entry.get("procedure"):
        return str(entry["procedure"]) in MOVERS
    act = entry.get("action") or {}
    return any(act.get(k) for k in _MOVE_KEYS)


def entry_opens(entry: dict[str, Any]) -> bool:
    return str(entry.get("procedure", "")) in OPENERS



def cell_of(pos: dict[str, Any] | None) -> tuple[int, int, int] | None:
    if not pos:
        return None
    try:
        return (int(pos["x"] // 8), int(pos["y"] // 8), int(pos["z"] // 8))
    except (KeyError, TypeError, ValueError):
        return None


class Governor:
    """Bookkeeping the model cannot do for itself: what ran, where, what it changed."""

    def __init__(self) -> None:
        # (label, cell) -> [null_streak, first_null_step, last_step]
        self._null: dict[tuple[str, tuple[int, int, int] | None], list[int]] = {}
        self._recent: deque[tuple[int, int, bool]] = deque()  # (step, events, null?)
        self._item_types: set[str] = set()
        self._milestones = 0
        self._milestone_step: int | None = None
        self.nudges = 0
        self.vetoes = 0
        # cell -> [null streak (any label), first null step, last step]
        self._cell_streak: dict[tuple[int, int, int], list[int]] = {}
        # cell -> the last step a productive entry finished there (or the first
        # step seen there), for the STALL_STEPS clock.
        self._cell_since: dict[tuple[int, int, int], int] = {}
        self.plan_stalls = 0

    # ---------------- classification ----------------

    def note_entry(self, *, label: str, cell: tuple[int, int, int] | None, step: int,
                   events: int, moved: float, descended: float,
                   inv_changed: bool, item_types: set[str],
                   milestones: int) -> str | None:
        """Record one finished entry. Returns a nudge note when a streak arms."""
        if milestones > self._milestones:
            self._milestones = milestones
            self._milestone_step = step
            self._aspire()
        if item_types - self._item_types:
            self._item_types |= item_types
            self._aspire()
        null = (events == 0 and not inv_changed
                and moved < NULL_MOVE_EPS and descended < NULL_DESCENT_EPS)
        self._recent.append((step, events, null))
        if cell is not None:
            if null:
                rec = self._cell_streak.get(cell)
                if rec is None:
                    self._cell_streak[cell] = [1, step, step]
                else:
                    rec[0] += 1
                    rec[2] = step
                self._cell_since.setdefault(cell, step)
            else:
                self._cell_streak.pop(cell, None)
                self._cell_since[cell] = step
        while self._recent and self._recent[0][0] < step - WINDOW_STEPS:
            self._recent.popleft()
        key = (label, cell)
        if not null:
            self._null.pop(key, None)
            return None
        rec = self._null.get(key)
        if rec is None:
            self._null[key] = [1, step, step]
            return None
        rec[0] += 1
        rec[2] = step
        if rec[0] == NUDGE_AT:
            self.nudges += 1
            return (f"governor: `{label}` at this spot has now finished {rec[0]} times "
                    f"in a row changing nothing -- no event, no inventory change, no "
                    f"real movement (since step {rec[1]}). A third identical proposal "
                    f"will be refused before it spends steps. Change the approach, the "
                    f"target, or the place.")
        return None

    def _aspire(self) -> None:
        """Aspiration: the world moved, so every standing ban is stale. Glover's
        criterion, coarse on purpose -- a new item type or milestone changes what
        every old null attempt would now mean."""
        self._null.clear()
        self._cell_streak.clear()

    # ---------------- enforcement ----------------

    def check(self, label: str, cell: tuple[int, int, int] | None,
              step: int) -> str | None:
        """Veto text if this (procedure, place) is banned, else None."""
        if label not in VETOABLE:
            return None
        rec = self._null.get((label, cell))
        if rec is None:
            return None
        if step - rec[2] > TENURE_STEPS:
            self._null.pop((label, cell), None)
            return None
        if rec[0] >= NUDGE_AT:
            self.vetoes += 1
            return (f"governor: REFUSED `{label}` here -- it has finished {rec[0]} "
                    f"times in a row at this spot changing nothing (since step "
                    f"{rec[1]}), so the entry was dropped before spending its steps. "
                    f"Known-null here stays null until something about the situation "
                    f"changes: new tool, new place, new target.")
        return None

    # ---------------- the ledger line ----------------

    def check_plan(self, entries: list[dict[str, Any]],
                   cell: tuple[int, int, int] | None, step: int,
                   gui_open: bool) -> str | None:
        """The stall verdict for a whole plan, or None to let it run.

        Fires when this cell has CELL_STREAK_VETO null entries in a row (any labels)
        or STALL_STEPS without a productive one, and the plan neither moves nor
        opens a screen. With a screen open the GUI work is exempt (the
        lesson of one run: banning cursor micro-ops broke a recovery); the clock still runs."""
        if cell is None or not entries:
            return None
        streak = self._cell_streak.get(cell)
        n = streak[0] if streak else 0
        since = self._cell_since.get(cell)
        stalled = (step - since) if since is not None else 0
        if n < CELL_STREAK_VETO and stalled < STALL_STEPS:
            return None
        if gui_open or any(entry_moves(e) or entry_opens(e) for e in entries):
            return None
        self.plan_stalls += 1
        labels = ", ".join(str(e.get("procedure") or "raw") for e in entries)
        return (f"governor: STALLED at this spot -- {n} entries in a row changed nothing "
                f"here (no event, no inventory change, no real movement) and nothing "
                f"has changed here for {stalled} steps (since step {since}). A plan from "
                f"a stalled spot must MOVE (go_to a cell you walked, mine_forward, "
                f"dig_down/stair_down) or OPEN a screen; this one ({labels}) does "
                f"neither, so it was dropped for one no-op."
                + (" You have been at this for over 1200 steps: change the OBJECTIVE, not "
                   "just the entry -- craft or place a new one instead of re-opening the "
                   "old, go to a known site, or bank what you already hold."
                   if stalled >= SWITCH_STEPS else ""))

    def summary(self, *, step: int, y: float | None, budget: int) -> str:
        if not self._recent:
            return ""
        events = sum(e for _, e, _ in self._recent)
        nulls = sum(1 for _, _, n in self._recent if n)
        total = len(self._recent)
        span = min(WINDOW_STEPS, step - self._recent[0][0] + 1) if total else 0
        parts = [f"Ledger, last {span} steps: {events} world-changing events across "
                 f"{total} entries; {nulls} entries changed nothing."]
        if self._milestone_step is not None:
            parts.append(f"Last milestone was {step - self._milestone_step} steps ago.")
        elif step > 1500:
            parts.append(f"No milestone yet in {step} steps.")
        if y is not None:
            parts.append(f"y={y:.0f}.")
        parts.append(f"Step {step} of {budget}.")
        return " ".join(parts)
