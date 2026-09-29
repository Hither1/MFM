"""Stage 19: a blocked go_to detours over the cells the avatar walked.

Across 1,148 blocked walks in the historical full runs, 30% of the targets were never
reached and the replay found a walked cell nearer the target reachable over the trail
in 65% of them. Here: the avatar walks an open L (its trail), a 2-high wall is built
across the straight line to the last target, and the go_to must stall, record the wall
cell, retreat along its own trail and arrive from the open side.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import SPAWN, P, Rig, main_guard

Y = 30


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    rig.fill(bx - 14, Y - 6, bz - 14, bx + 14, Y + 6, bz + 14, "stone")
    rig.fill(bx - 11, Y, bz - 11, bx + 11, Y + 1, bz + 11, "air")
    for zz in range(bz - 10, bz + 11, 3):
        rig.fill(bx - 10, Y + 2, zz, bx + 10, Y + 2, zz, "glowstone")
    # the wall: x = bx, from z = bz - 4 to the north edge, two high
    rig.fill(bx, Y, bz - 4, bx, Y + 1, bz + 11, "cobblestone")
    ax, az = bx - 6.5, bz + 2.5          # A': the trail's start, 4 blocks south of D
    rig.tp(ax, Y, az, yaw=180, pitch=0)  # facing -z
    rig.clear()
    rig.give("iron_pickaxe", 1)
    rig.idle(20)
    grid = rig.agent.grid

    legs = [("south", bx - 6.5, bz - 6.5), ("east", bx + 6.5, bz - 6.5),
            ("north", bx + 6.5, bz + 6.5)]
    for name, tx, tz in legs:
        r = rig.run([P("go_to", x=tx, z=tz, within=0.8, n=240)], label=f"leg {name}",
                    max_ticks=300)
        p = rig.pos()
        rig.check(f"trail {name}: arrived", p is not None
                  and math.hypot(p["x"] - tx, p["z"] - tz) <= 1.2, p)
    rig.check("trail: 30+ walked cells on the map", len(grid.walked) >= 30, grid.audit())
    rig.frame("s19_before")

    dx_, dz_ = bx - 6.5, bz + 6.5        # D: west of C, behind the wall
    r = rig.run([P("go_to", x=dx_, z=dz_, within=1.0, n=240)], label="go_to D through the wall",
                max_ticks=700)
    p = rig.pos()
    rig.frame("s19_after")
    rig.check("detour: the walk stalled at the wall and detoured",
              r["stats"].get("goto_detours", 0) == 1
              and any("detouring over" in n for n in r["notes"]), (r["stats"], r["notes"][-2:]))
    rig.check("detour: the wall cell is on the map as blocked",
              any(c[0] == bx - 1 or c[0] == bx for c in grid.blocked), list(grid.blocked)[:4])
    rig.check("detour: arrived at D from the open side",
              p is not None and math.hypot(p["x"] - dx_, p["z"] - dz_) <= 1.5
              and r["stats"].get("goto_detour_arrived", 0) == 1, (p, r["stats"]))
    rig.check("detour: within the plan's ticks (< 600)", r["ticks"] < 600, r["ticks"])


if __name__ == "__main__":
    main_guard(stage)
