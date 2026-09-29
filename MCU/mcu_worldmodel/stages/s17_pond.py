"""Stage 17: the pond trap, and the walk out of it along the avatar's own trail.

39 half runs: a median 612 steps between the bucket fill and the first descent (ob3
2981, hd41z 3833), spent beside the pond with `dig_down` refused ("water within reach")
and every `go_to` away blocked by the shore. The runner had walked from dry ground to
the pond a moment earlier. Here: a lit stone hall at y 30 with a 3x3 pond flush with
the floor; the avatar walks 12 blocks to the rim (the trail), fills the bucket, asks
to dig -- the refusal must queue the walk back along the trail to a cell 8+ blocks
from the water, and the next dig must go down.
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
    # the hall: stone all round, 2 high, lit
    rig.fill(bx - 18, Y - 6, bz - 7, bx + 12, Y + 6, bz + 7, "stone")
    rig.fill(bx - 16, Y, bz - 4, bx + 10, Y + 1, bz + 4, "air")
    for xx in range(bx - 15, bx + 10, 3):
        rig.fill(xx, Y + 2, bz - 3, xx, Y + 2, bz + 3, "glowstone")
    # the pond: 3x3 water flush with the floor, its west edge at x = bx + 3
    rig.fill(bx + 3, Y - 1, bz - 1, bx + 5, Y - 1, bz + 1, "water")
    rig.tp(bx - 11.5, Y, bz + 0.5, yaw=-90, pitch=0)      # facing +x, the pond
    rig.clear()
    rig.give("bucket", 1)
    rig.give("iron_pickaxe", 1)
    rig.idle(20)
    rig.frame("s17_start")
    grid = rig.agent.grid

    r = rig.run([P("go_to", x=bx + 1.5, z=bz + 0.5, within=0.8, n=240)],
                label="walk to the rim", max_ticks=300)
    p = rig.pos()
    rig.check("trail: the walk reached the rim (x >= bx + 0.5)",
              p is not None and p["x"] >= bx + 0.5, p)
    rig.check("trail: the map holds the walked cells (10+)", len(grid.walked) >= 10,
              grid.audit())

    r = rig.run([P("fill_bucket")], label="fill_bucket at the rim", max_ticks=320)
    rig.frame("s17_filled")
    rig.check("fill: water_bucket in the inventory", r["inv"].get("water_bucket", 0) >= 1,
              (r["inv"], r["notes"][-1:]))
    rig.check("fill: the map recorded water cells", len(grid.water) >= 1, grid.audit())

    from mcu_worldmodel.stages.rig import hotbar_of
    pick = hotbar_of(rig, "iron_pickaxe") or 2
    r = rig.run([P("equip_hotbar", slot=pick), P("dig_down", n=120, until_y=Y - 8)],
                label="dig_down beside the pond", max_ticks=500)
    p = rig.pos()
    rig.frame("s17_after_refusal")
    rig.check("refusal: dig_down was refused for the water",
              any("dig_down REFUSED: water" in n for n in r["notes"]), r["notes"][-2:])
    rig.check("escape: the runner queued the walk along the trail",
              r["stats"].get("water_escapes", 0) == 1
              and any("along your own trail" in n for n in r["notes"]), r["stats"])
    rig.check("escape: the avatar ended 8+ blocks west of the rim (x <= bx - 6.5)",
              p is not None and p["x"] <= bx - 6.5 and abs(p["y"] - Y) < 0.6, p)
    rig.check("escape: the plan drained in under 300 ticks", r["drained"] and r["ticks"] < 300,
              r["ticks"])

    y0 = (rig.pos() or {}).get("y", Y)
    r = rig.run([P("equip_hotbar", slot=pick), P("dig_down", n=200, until_y=Y - 4)],
                label="dig_down from dry ground", max_ticks=400)
    p = rig.pos()
    rig.frame("s17_dug")
    rig.check("dig: not refused this time",
              not any("REFUSED: water" in n for n in r["notes"]), r["notes"][-2:])
    rig.check("dig: went down 3+ blocks", p is not None and y0 - p["y"] >= 3.0, (y0, p))


if __name__ == "__main__":
    main_guard(stage)
