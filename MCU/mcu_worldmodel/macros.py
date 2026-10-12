"""Registry for closed-loop markers implemented outside agent.py.

The runner resolves a queue entry that is a *marker* (`{"_servo": {...}, "_cost": 16}`)
one tick at a time against the current observation. The original markers are methods
on `WorldModelAgent` and are dispatched from a table inside `next_action`; every new
macro used to mean one more entry in that table, one more `_SHRINKABLE` line and one
more name in the repeat-hit movement list -- three edits to the busiest file in the
package for each of the twenty-odd macros the dragon chain needs.

This module is the seam: a macro module registers its tick function under its marker
key with `@tick("_key")`, the runner falls through to `TICKS` for any key its own table
does not know, `shrink_marker` reads `SHRINK` for the field that holds the tick budget,
and the repeat-hit rule reads `MOVING` for the markers that move the avatar. agent.py
is edited once, here, and never again for a macro.

A tick function has the signature `fn(agent, payload, mk_act) -> action | None`: it
reads the runner's state through the agent (`agent._cur_pos`, `agent._cur_inv`,
`agent._gui_open`, `agent._screen`, `agent._last_pov`, `agent.stat_now(...)`), writes
notes with `agent.memory.add_note`, stops the rest of a plan with `agent._flush_tail`,
and returns the env action for this tick or None when the marker is finished.
"""
from __future__ import annotations

from typing import Any, Callable

#: marker key -> tick function (see the module docstring for the signature).
TICKS: dict[str, Callable[..., Any]] = {}
#: marker key -> the payload field holding the tick budget, for `shrink_marker`.
SHRINK: dict[str, str] = {}
#: marker keys whose ticks move the avatar (the repeat-hit rule keeps those running).
MOVING: set[str] = set()
#: Marker keys that ARE the response to being attacked (a fight, a shield block, a
#: bow shot, an entity right-click). The runner's hit reflex turns the avatar 180
#: degrees away from the hit and clears the plan -- exactly the wrong move while a
#: macro is aiming at the mob that swung. These keep running instead, above the
#: critical-health line; the pillar escape below it still wins.
COMBAT: set[str] = set()
#: Screen kinds (vision.screen_kind names) whose block keeps what sits in its cells
#: when the screen closes: a close is lossless for them, and the runner's drop guard
#: and its "on the floor" note stand down. A container module adds its kinds here.
KEEPS_CONTENTS: set[str] = {"furnace"}


def tick(key: str, *, shrink: str | None = None, moving: bool = False,
         combat: bool = False):
    """Register the decorated function as the runner's tick for marker `key`."""
    if not key.startswith("_"):
        raise ValueError(f"marker keys start with '_': {key!r}")

    def deco(fn):
        TICKS[key] = fn
        if shrink:
            SHRINK[key] = shrink
        if moving:
            MOVING.add(key)
        if combat:
            COMBAT.add(key)
        return fn
    return deco


def marker(key: str, payload: dict[str, Any], cost: int) -> dict[str, Any]:
    """One queue entry: the payload under `key`, charged `cost` ticks by the step cap."""
    return {key: dict(payload), "_cost": max(0, int(cost))}


def kind_of(head: Any) -> str | None:
    """The registered marker key in a queue entry, or None."""
    if not isinstance(head, dict):
        return None
    for k in head:
        if k in TICKS:
            return k
    return None
