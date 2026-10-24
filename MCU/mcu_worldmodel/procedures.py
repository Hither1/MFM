"""The env action every plan entry is built from, and what a procedure call meets.

`MinecraftSim` exposes no crafting action, no walk-to and no aim: a recipe is performed
the way a human performs it -- a screen, a cursor, clicks -- and a walk is keys held over
ticks. No arm is given any of that as a named macro. Every entry the model writes is a
raw action held for N ticks or, in the mfm arm, one of its own scripts under
`mine/procedures/` (mcu_worldmodel/own.py), which returns raw actions too. A procedure
call of any other name is refused with a [NOTE] (`refusal`), never silently.
"""
from __future__ import annotations

from typing import Any


def noop() -> dict[str, Any]:
    """One env action with nothing pressed -- built fresh each call because these go
    into a list that the runner mutates."""
    a = {k: 0 for k in (
        "attack", "back", "forward", "jump", "left", "right", "sneak", "sprint", "use",
        "inventory", *(f"hotbar.{i}" for i in range(1, 10)),
    )}
    a["camera"] = [0.0, 0.0]
    return a


def act(**kw) -> dict[str, Any]:
    a = noop()
    for k, v in kw.items():
        key = k.replace("hotbar_", "hotbar.")
        if key == "camera":
            a["camera"] = [float(v[0]), float(v[1])]
        else:
            a[key] = int(v)
    return a


#: Whether the arm keeps procedures of its own (`own`): the refusal offers that way out
#: only where it exists.
OWN: bool = True


def set_own(own: bool) -> None:
    global OWN
    OWN = bool(own)


def refusal(name: str) -> str:
    """The [NOTE] for a call of a procedure that is not one of the model's own."""
    return (f"{name!r}: this run has no built-in procedures -- build it from raw actions"
            + (", as your own procedure under mine/procedures/" if OWN else ""))
