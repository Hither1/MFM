"""Stage 24: the fall guard stops the plan on landing after an unplanned drop.

og13_mfm (2026-09-07, 18768-18818, the Nether): a go_to dropped 13 blocks into a hole,
the plan went on, the model jumped onward and fell again, dead with the kit. Here a
lit platform A stands six blocks above a second platform B beyond its south edge. Raw
`forward` held off A's edge must end with one FELL note on B and the rest of the plan
dropped; a stair_down dug into A's solid base (a walked descent) must not fire.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 80, -5450
DROP = 6


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    # A: floor at Y on a solid base (a stair can be dug into it); B: floor at Y-DROP, z Z+5..Z+13
    rig.fill(X - 4, Y - 12, Z - 4, X + 4, Y, Z + 4, "stone")
    rig.fill(X - 4, Y + 1, Z - 4, X + 4, Y + 8, Z + 4, "air")
    rig.fill(X - 4, Y - DROP - 3, Z + 5, X + 4, Y - DROP, Z + 13, "stone")
    rig.fill(X - 4, Y - DROP + 1, Z + 5, X + 4, Y + 8, Z + 13, "air")
    for xx in (X - 3, X + 3):
        rig.fill(xx, Y + 5, Z - 3, xx, Y + 5, Z + 12, "glowstone")
    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=0)         # facing +z, the edge 4 blocks on
    rig.clear()
    rig.give("stone_pickaxe", 1)
    rig.idle(12)
    y0 = rig.pos()["y"]

    r1 = rig.run([{"action": {"forward": 1}, "repeat": 60}, {"action": {"jump": 1}, "repeat": 4}],
                 label="raw forward off the edge", max_ticks=120)
    p = rig.pos()
    notes = [n for n in r1["notes"] if n.startswith("FELL")]
    rig.check("the avatar landed on B, DROP blocks lower", abs(p["y"] - (y0 - DROP)) < 0.6, (y0, p))
    rig.check("one FELL note names the drop and the landing",
              len(notes) == 1 and f"FELL {DROP} blocks" in notes[0]
              and f"({X}, {int(y0 - DROP)}, " in notes[0], notes[:1] or r1["notes"][-3:])
    rig.check("the rest of the plan was dropped (fall_stops 1, queue drained early)",
              r1["stats"].get("fall_stops") == 1 and r1["drained"] and r1["ticks"] < 60,
              (r1["stats"], r1["ticks"]))

    # a walked descent: a stair dug into A's base does not fire
    rig.tp(X + 0.5, Y + 1, Z - 2.5, yaw=180, pitch=0)       # facing -z, away from the edge
    rig.idle(12)
    pick = next((h["slot"] for h in __import__("mcu_worldmodel.episodes", fromlist=["_hotbar"])
                 ._hotbar(rig.info) if "pickaxe" in h["item"]), 0)
    r2 = rig.run([P("equip_hotbar", slot=pick + 1), P("stair_down", depth=4, ore_watch=False)],
                 label="stair_down into the base", max_ticks=700)
    p = rig.pos()
    rig.check("stair_down descended without a FELL stop",
              p["y"] < y0 - 1.5 and not r2["stats"].get("fall_stops"), (p, r2["stats"]))
    rig.frame("s24_after")


if __name__ == "__main__":
    main_guard(stage)
