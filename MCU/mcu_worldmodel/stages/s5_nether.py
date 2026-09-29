"""Stage 5: obsidian, the portal frame, lighting it, and the trip to the Nether.

From a prepared state on the platform: a 3x3 lava pool beside a stone rim, a water
bucket -> make_obsidian turns the sources to obsidian (checked by mining one with a
diamond pickaxe: mine_block obsidian, pickup obsidian); 14 obsidian + flint_and_steel ->
build_portal_frame (use_item.obsidian +14), light_portal (use_item.flint_and_steel +1 and
portal purple in the frame), enter_portal (biome id / position jump -> "the Nether"),
then netherrack is mined and picked up, and the way back is the same portal.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard, slot_of


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=12, block="stone", clear_to=10)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.idle(10)

    # -- obsidian from lava: a 3x3 lava pool sunk one level below the platform, 3 ahead --
    rig.fill(bx - 1, by - 1, bz + 3, bx + 1, by - 1, bz + 5, "air")
    rig.fill(bx - 1, by - 2, bz + 3, bx + 1, by - 2, bz + 5, "lava")
    rig.give("water_bucket", 1)
    rig.give("diamond_pickaxe", 1)
    rig.idle(10)
    rig.frame("s5_lava")
    r = rig.run([P("make_obsidian", x=bx, y=by - 1, z=bz + 2)], label="make_obsidian",
                max_ticks=300)
    rig.check("make_obsidian: the water went out and came back",
              r["inv"].get("water_bucket", 0) == 1 and any("obsidian now" in n for n in r["notes"]),
              (r["inv"], r["notes"]))
    rig.frame("s5_after_pour")
    s0 = rig.stats()
    r = rig.run([P("mine_obsidian", x=bx, y=by - 2, z=bz + 3)], label="mine_obsidian",
                max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("mine_obsidian: an obsidian block broke (the drop lies in the sunk pool)",
              d.get("mine_block.obsidian", 0) >= 1, (d, r["inv"], r["notes"]))
    rig.frame("s5_mined")
    rig.fill(bx - 2, by - 2, bz + 1, bx + 2, by - 1, bz + 6, "stone")
    rig.fill(bx - 2, by, bz + 1, bx + 2, by + 2, bz + 6, "air")

    # -- the frame, 14 obsidian, 2 blocks ahead across the facing ----------------------
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.give("obsidian", 14)
    rig.give("flint_and_steel", 1)
    rig.give("cobblestone", 8)
    rig.idle(8)
    s0 = rig.stats()
    r = rig.run([P("build_portal_frame", dist=2)], label="build_portal_frame (1)",
                max_ticks=900)
    r2 = rig.run([P("build_portal_frame", dist=2)], label="build_portal_frame (2)",
                 max_ticks=900)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("build_portal_frame: 14 obsidian placed over two calls",
              d.get("use_item.obsidian") == 14.0, (d, r["notes"], r2["notes"]))
    rig.frame("s5_frame")
    s0 = rig.stats()
    r = rig.run([P("light_portal", dist=2)], label="light_portal", max_ticks=200)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("light_portal: flint_and_steel used and the portal reads LIT",
              d.get("use_item.flint_and_steel") == 1.0 and any("LIT" in n for n in r["notes"]),
              (d, r["notes"]))
    rig.frame("s5_lit")
    over = rig.pos()
    r = rig.run([P("enter_portal", dist=2)], label="enter_portal", max_ticks=400)
    p = rig.pos()
    # biome_id reads 0 in both dimensions in this engine (measured 2026-09-03); the
    # coordinates divide by 8 on arrival, and the macro's note says so.
    rig.check("enter_portal: the note says the Nether and the coordinates are /8",
              any("in the Nether" in n for n in r["notes"])
              and abs(p["x"] - over["x"] / 8) < 32 and abs(p["z"] - over["z"] / 8) < 32,
              (over, p, r["notes"]))
    rig.frame("s5_nether")

    # -- netherrack: step off the portal's obsidian platform, then mine the ground ---------
    rig.give("diamond_pickaxe", 1)
    rig.idle(5)
    pick = slot_of(rig, "diamond_pickaxe")
    nether_pos = rig.pos()
    s0 = rig.stats()
    # The arrival platform is obsidian; the ground a block or two out is netherrack.
    # No blind walking (the portal can stand on a ledge: a 30-tick sprint fell 8 blocks
    # in pass 7): swing at the ground ahead at 40 degrees in up to three headings.
    got = False
    for yaw_off in (0.0, 90.0, -90.0):
        r = rig.run([P("equip_hotbar", slot=(pick + 1) if pick is not None else 1),
                     P("look_abs", pitch=40, yaw=nether_pos["yaw"] + yaw_off),
                     P("mine_until", item="netherrack", n=1, ticks=300)],
                    label=f"mine netherrack (yaw {yaw_off:+.0f})", max_ticks=400)
        if r["inv"].get("netherrack", 0) >= 1:
            got = True
            break
        rig.run([P("collect_drops", ticks=40)], label="sweep", max_ticks=80)
        if rig.inv().get("netherrack", 0) >= 1:
            got = True
            break
    d = rig.stat_delta(s0, rig.stats())
    rig.check("netherrack picked up in the Nether", got or d.get("pickup.netherrack", 0) >= 1,
              (d, rig.inv()))
    rig.frame("s5_netherrack")

    # -- and back through the same portal (its cell on this side is where we arrived) ------
    r = rig.run([P("enter_portal", x=nether_pos["x"], z=nether_pos["z"])],
                label="enter_portal (back)", max_ticks=400)
    p = rig.pos()
    rig.check("the way back: the note says the Overworld and the coordinates are x8",
              any("in the Overworld" in n for n in r["notes"])
              and abs(p["x"] - over["x"]) < 40 and abs(p["z"] - over["z"]) < 40,
              (p, r["notes"]))


if __name__ == "__main__":
    main_guard(stage)
