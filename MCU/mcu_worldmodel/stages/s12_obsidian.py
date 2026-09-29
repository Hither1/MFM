"""Stage 12: obsidian from a lava LAKE at floor level, the way the runs meet it.

Stage s5 verified the pour and the mine on a 3x3 pool sunk one level, from a rim named
by hand. The 148 dragon runs never had that: their lakes were at floor level, sighted
by the runner's LAVA AHEAD guard (never by find_lava), and after the pour the flow
pushed the avatar off the rim, the scoop was refused as out of reach, the mined cell
was one off, and mine_obsidian was shrunk under the 190 ticks a block takes. This
stage builds that situation and runs the 2026-09-06 macros through it:

1. a 5x5 lava lake flush with the platform floor, 4 blocks ahead; walk toward it with
   the water bucket carried until the guard fires -> LAVA AHEAD names pool and rim and
   `macros_nether.LAST_LAVA` holds them;
2. `make_obsidian()` with NO arguments: pour on that rim, scoop back (closed loop),
   drain -> water_bucket back in the inventory;
3. `mine_obsidian()` with NO arguments: the sighting's pool cell -> `mine_block obsidian`
   moves (the milestone's event);
4. a second block by coordinates, mine_obsidian(x, y, z) on a neighbouring source cell;
5. the plan-cap rule: a plan whose tail leaves under 240 ticks drops mine_obsidian whole
   with the NOT STARTED note rather than a stub.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard


#: The room's floor level: the runner's lava guard watches only below y 40 (a surface
#: lake is not the situation the runs meet), and 11 is where the lakes are.
Y = 11
LAKE_DZ = 4


def _room(rig: Rig, bx: int, bz: int) -> None:
    """A lit stone room 9 wide, 2 high, 30 long at Y, solid rock all round (s11's)."""
    rig.fill(bx - 8, Y - 8, bz - 6, bx + 8, Y + 8, bz + 34, "stone")
    rig.fill(bx - 4, Y, bz - 4, bx + 4, Y + 1, bz + 30, "air")
    for zz in range(bz - 4, bz + 30, 3):
        rig.fill(bx - 3, Y + 2, zz, bx + 3, Y + 2, zz, "glowstone")


def stage(rig: Rig) -> None:
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel.actions import parse_actions

    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    _room(rig, bx, bz)
    # A 5x5 lake of lava SOURCES flush with the floor, its near edge LAKE_DZ ahead;
    # stone all round it at that level, so nothing flows and the sources stay sources.
    rig.fill(bx - 2, Y - 1, bz + LAKE_DZ, bx + 2, Y - 1, bz + LAKE_DZ + 4, "lava")
    rig.tp(bx + 0.5, Y, bz + 0.5, yaw=0, pitch=8)
    rig.clear()
    rig.give("water_bucket", 1)
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 16)
    rig.idle(20)
    rig.frame("s12_lake")
    MN.LAST_LAVA = None
    y = float(Y)

    # 1. the guard: walk toward the lake; the runner must stop the walk and name the cells
    r = rig.run([RAW(60, forward=1)], label="walk at the lake (guard)", max_ticks=120)
    p = rig.pos()
    rig.check("guard: LAVA AHEAD fired and the avatar is still on stone (y unchanged)",
              any("LAVA AHEAD" in n for n in r["notes"]) and p and abs(p["y"] - y) < 0.6
              and p["z"] < bz + LAKE_DZ, (p, r["notes"][-1:] if r["notes"] else r))
    rig.check("guard: the sighting is on record with pool and rim cells",
              MN.LAST_LAVA is not None and MN.LAST_LAVA["source"] == "guard",
              MN.LAST_LAVA)
    rig.check("guard: the note tells the model the no-argument calls use these cells",
              any("make_obsidian()" in n for n in r["notes"]), r["notes"][-1:])
    if MN.LAST_LAVA:
        pool, rim = MN.LAST_LAVA["pool"], MN.LAST_LAVA["rim"]
        rig.log(f"sighting: pool {pool} rim {rim} from {rig.pos()}")
        rig.check("geometry: the pool cell is lava and the rim cell is stone, one apart",
                  pool[1] == Y - 1 and rim[1] == Y - 1
                  and bz + LAKE_DZ <= pool[2] <= bz + LAKE_DZ + 4
                  and rim[2] == pool[2] - 1 and abs(pool[0] - bx) <= 2, (pool, rim))

    # 2. the pour by the record: make_obsidian() with no arguments
    s0 = rig.stats()
    r = rig.run([P("make_obsidian")], label="make_obsidian()", max_ticks=400)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s12_after_pour")
    rig.check("make_obsidian(): the water went out and came back",
              d.get("use_item.water_bucket", 0) >= 1 and r["inv"].get("water_bucket", 0) == 1,
              (d, r["inv"], r["notes"]))
    rig.check("make_obsidian(): the closed-loop scoop reported it",
              any("back in the bucket" in n for n in r["notes"]), r["notes"])

    # 3. the mine by the record: mine_obsidian() with no arguments
    s0 = rig.stats()
    r = rig.run([P("mine_obsidian")], label="mine_obsidian()", max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s12_mined")
    rig.check("mine_obsidian(): mine_block obsidian moved (the milestone's event)",
              d.get("mine_block.obsidian", 0) >= 1, (d, r["inv"], r["notes"]))
    rig.check("mine_obsidian(): the note says OBSIDIAN BROKEN",
              any("OBSIDIAN BROKEN" in n for n in r["notes"]), r["notes"])

    # 4. a neighbour by coordinates (the lake's other sources are obsidian too)
    if MN.LAST_LAVA:
        pool = MN.LAST_LAVA["pool"]
        nb = (pool[0] + 1 if pool[0] < bx + 2 else pool[0] - 1, pool[1], pool[2])
        s0 = rig.stats()
        r = rig.run([P("mine_obsidian", x=nb[0], y=nb[1], z=nb[2])],
                    label="mine_obsidian(x, y, z) neighbour", max_ticks=500)
        d = rig.stat_delta(s0, rig.stats())
        rig.check("a second block by coordinates broke",
                  d.get("mine_block.obsidian", 0) >= 1, (nb, d, r["notes"]))
    rig.check("obsidian in the inventory after the sweeps",
              rig.inv().get("obsidian", 0) >= 1, rig.inv())

    # 5. the plan-cap rule, at the parser
    plan = ('{"actions": [{"procedure": "travel", "args": {"n": 300}}, '
            '{"procedure": "mine_obsidian"}]}')
    out = parse_actions(plan, info=rig.info, step_cap=400)
    rig.check("plan cap: mine_obsidian behind 300 ticks is dropped whole, not shrunk",
              [e["procedure"] for e in out.entries] == ["travel"]
              and any("'mine_obsidian' NOT STARTED" in n for n in out.notes), out.notes)


if __name__ == "__main__":
    main_guard(stage)
