"""Stage 2: the world macros against the real engine.

On a flat stone platform: place a block by coordinate (and be refused for the cell the
avatar stands in), stack a second on top, hang a torch on its side, build a 5x2 wall and
a 4-long row, pillar up three and dig back down, bridge across a trench, pour and refill
a water bucket, till and sow, shear a pumpkin, light the ground, throw snowballs, draw
the bow, eat, scan around, and sleep in a bed at night. Every check reads statistics,
the inventory or the position -- never the frame alone.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard, slot_of


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)

    def home(yaw: float = 0.0) -> None:
        """Clear the spawn column and put the avatar back at the platform centre."""
        rig.fill(bx - 1, by, bz - 1, bx + 1, by + 6, bz + 1, "air")
        rig.tp(x, y, z, yaw=yaw, pitch=0)
        rig.idle(6)
        p = rig.pos()
        rig.check(f"home: back at the centre (yaw {yaw:.0f})",
                  abs(p["x"] - x) < 0.2 and abs(p["z"] - z) < 0.2 and abs(p["y"] - y) < 0.2, p)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=10, block="stone", clear_to=8)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.give("cobblestone", 64)
    rig.give("torch", 8)
    rig.idle(10)

    # -- place_at: the block two ahead, the cell we stand in (refused), one on top ------
    s0 = rig.stats()
    r = rig.run([P("place_at", x=bx, y=by, z=bz + 2, item="cobblestone")], label="place_at ahead")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("place_at: use_item.cobblestone +1", d.get("use_item.cobblestone") == 1.0, d)
    rig.check("place_at: note says placed", any("placed at" in n for n in r["notes"]), r["notes"])
    rig.frame("s2_place_ahead")
    r = rig.run([P("place_at", x=bx, y=by, z=bz, item="cobblestone")], label="place_at own cell")
    rig.check("place_at refuses the cell you stand in",
              any("where YOU stand" in n for n in r["notes"]), r["notes"])
    s0 = rig.stats()
    r = rig.run([P("place_at", x=bx, y=by + 1, z=bz + 2, item="cobblestone")], label="place_at on top")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("place_at on top of the placed block", d.get("use_item.cobblestone") == 1.0, d)
    # a torch on the column's near (north) face: target cell (bx, by+1, bz+1), support south
    s0 = rig.stats()
    r = rig.run([P("use_at", x=bx, y=by + 1, z=bz + 1, item="torch", face="south")],
                label="torch on the wall face")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("use_at: torch on a wall face (use_item.torch +1)", d.get("use_item.torch") == 1.0, d)
    rig.frame("s2_torch")
    rig.fill(bx - 1, by, bz + 1, bx + 1, by + 3, bz + 3, "air")

    # -- build_wall facing west (yaw 90): 5 wide x 2 high, 2 blocks ahead ------------------
    home(90)
    s0 = rig.stats()
    r = rig.run([P("build_wall", item="cobblestone", length=5, height=2, dist=2)],
                label="build_wall 5x2", max_ticks=900)
    d = rig.stat_delta(s0, rig.stats())
    # 10 wall blocks + 1 pillar block the upper row is built from
    rig.check("build_wall: 10 blocks placed (+1 to stand on)", d.get("use_item.cobblestone") == 11.0, d)
    rig.check("build_wall: both rows report 5 of 5",
              sum(1 for n in r["notes"] if "placed 5 of 5" in n) == 2, r["notes"])
    rig.frame("s2_wall")
    rig.fill(bx - 4, by, bz - 4, bx - 1, by + 3, bz + 4, "air")

    # -- build_row facing north (yaw 180): 4 blocks, far cells first --------------------
    home(180)
    s0 = rig.stats()
    r = rig.run([P("build_row", item="cobblestone", length=4)], label="build_row 4", max_ticks=900)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("build_row: 4 blocks placed", d.get("use_item.cobblestone") == 4.0, d)
    rig.frame("s2_row")
    rig.fill(bx - 1, by, bz - 6, bx + 1, by + 1, bz - 1, "air")

    # -- pillar_up 3, then dig back down ----------------------------------------------------
    home(0)
    rig.give("stone_pickaxe", 1)
    rig.idle(4)
    y0 = rig.pos()["y"]
    r = rig.run([P("pillar_up", n=3)], label="pillar_up 3")
    rig.check("pillar_up: y rose by 3", abs(rig.pos()["y"] - (y0 + 3)) < 0.3, (y0, rig.pos()))
    rig.check("pillar_up: note says 3 of 3", any("3 of 3" in n for n in r["notes"]), r["notes"])
    rig.frame("s2_pillar")
    pick = slot_of(rig, "stone_pickaxe")
    # The first cobblestone mined fires the mine_cobblestone milestone (this rig runs the
    # dragon config), which drops the running plan by design: dig twice if needed.
    for _ in range(2):
        r = rig.run([P("equip_hotbar", slot=(pick + 1) if pick is not None else 1),
                     P("dig_down", n=200, until_y=y0 + 0.5)], label="dig back down",
                    max_ticks=400)
        if rig.pos()["y"] <= y0 + 0.5:
            break
    rig.check("dig_down returns to the floor", rig.pos()["y"] <= y0 + 0.5, rig.pos())

    # -- bridge_forward over a trench (facing +z) ----------------------------------------
    home(0)
    rig.fill(bx - 2, by - 1, bz + 1, bx + 2, by - 1, bz + 6, "air")       # a 6-long trench
    rig.fill(bx - 2, by - 2, bz + 1, bx + 2, by - 2, bz + 6, "air")
    rig.idle(5)
    s0 = rig.stats()
    r = rig.run([P("bridge_forward", n=4, item="cobblestone")], label="bridge_forward 4",
                max_ticks=900)
    d = rig.stat_delta(s0, rig.stats())
    p = rig.pos()
    rig.check("bridge_forward: 4 blocks placed", d.get("use_item.cobblestone") == 4.0, d)
    rig.check("bridge_forward: the avatar advanced ~3-4 blocks on the bridge",
              p["z"] - z >= 2.5 and abs(p["y"] - y) < 0.3, p)
    rig.frame("s2_bridge")
    rig.fill(bx - 2, by - 2, bz + 1, bx + 2, by - 1, bz + 6, "stone")
    rig.fill(bx - 2, by, bz + 1, bx + 2, by + 1, bz + 6, "air")

    # -- water bucket: pour and refill ------------------------------------------------------
    home(0)
    rig.clear()
    rig.give("water_bucket", 1)
    rig.give("cobblestone", 16)
    rig.idle(5)
    s0 = rig.stats()
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 3, item="water_bucket")], label="pour water")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("water poured (use_item.water_bucket, bucket back)",
              d.get("use_item.water_bucket") == 1.0 and r["inv"].get("bucket", 0) == 1, (d, r["inv"]))
    rig.frame("s2_water")
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 3, item="bucket", face="above")], label="refill")
    rig.check("bucket refilled (water_bucket back)", r["inv"].get("water_bucket", 0) == 1, r["inv"])
    # -- fill_bucket: the closed-loop sweep, no cell or face named ---------------------------
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 3, item="water_bucket")], label="pour again")
    rig.check("water poured again for the sweep (bucket empty)", r["inv"].get("bucket", 0) == 1, r["inv"])
    home(0)
    r = rig.run([P("fill_bucket")], label="fill_bucket sweep")
    rig.check("fill_bucket finds the source ahead and fills (water_bucket back)",
              r["inv"].get("water_bucket", 0) == 1 and any("the bucket filled -- water_bucket" in n for n in r["notes"]),
              (r["inv"], r["notes"][-3:]))
    rig.frame("s2_fill_bucket")
    rig.fill(bx - 3, by, bz + 1, bx + 3, by + 1, bz + 6, "air")
    # -- fetch_water: a pool 8-10 blocks north behind a two-high leaf hedge, seen from a
    # three-block mound (the sight line over the hedge reaches the ground at 7 blocks) --
    rig.clear()
    rig.give("bucket", 1)
    rig.give("cobblestone", 16)
    rig.fill(bx - 1, by - 1, bz + 8, bx + 1, by - 1, bz + 10, "water")
    rig.fill(bx - 4, by, bz + 4, bx + 4, by + 1, bz + 4, "spruce_leaves")
    rig.fill(bx, by, bz, bx, by + 2, bz, "stone")
    rig.tp(x, y + 3, z, yaw=0, pitch=0)
    rig.idle(8)
    s0 = rig.stats()
    r = rig.run([P("fetch_water")], label="fetch_water", max_ticks=1200)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("fetch_water walks to the pool through the hedge and the sweep fills the bucket",
              r["inv"].get("water_bucket", 0) == 1
              and any("water reached" in n for n in r["notes"])
              and any("the bucket filled -- water_bucket" in n for n in r["notes"]),
              (r["inv"], r["notes"][-4:]))
    rig.check("fetch_water broke a hedge block on the way (mine_block.spruce_leaves)",
              d.get("mine_block.spruce_leaves", 0) >= 1, d)
    p = rig.pos()
    rig.check("fetch_water stopped on the shore, not in the pool (z short of the water)",
              p is not None and p["z"] < bz + 8.0 and p["z"] > bz + 4.5, p)
    rig.frame("s2_fetch_water")
    rig.fill(bx - 1, by - 1, bz + 8, bx + 1, by - 1, bz + 10, "stone")
    rig.fill(bx - 4, by, bz + 4, bx + 4, by + 2, bz + 4, "air")
    rig.fill(bx, by, bz, bx, by + 2, bz, "air")

    # -- hoe + seeds on a grass block; shears on a pumpkin; flint and steel ------------------
    home(0)
    rig.clear()
    rig.give("iron_hoe", 1)
    rig.give("wheat_seeds", 8)
    rig.give("shears", 1)
    rig.give("flint_and_steel", 1)
    rig.setblock(bx, by - 1, bz + 2, "grass_block")
    rig.idle(5)
    r = rig.run([P("use_at", x=bx, y=by - 1, z=bz + 2, item="iron_hoe", face="above")],
                label="hoe the grass")
    rig.check("hoe: note says used", any("used at" in n for n in r["notes"]), r["notes"])
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 2, item="wheat_seeds")], label="sow seeds")
    rig.check("seeds planted (wheat_seeds -1)", r["inv"].get("wheat_seeds", 0) == 7, r["inv"])
    rig.frame("s2_farm")
    rig.setblock(bx, by, bz + 2, "air")
    rig.setblock(bx, by - 1, bz + 2, "stone")
    rig.setblock(bx, by + 1, bz + 3, "pumpkin")
    rig.idle(5)
    s0 = rig.stats()
    r = rig.run([P("use_at", x=bx, y=by + 1, z=bz + 2, item="shears", face="south")],
                label="shear the pumpkin")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("pumpkin sheared (the shears took wear; use_item.shears does not count it)",
              any("took wear" in n for n in r["notes"]), (d, r["inv"], r["notes"]))
    r = rig.run([RAW(24, forward=1), P("collect_drops", ticks=60)], label="sweep the seeds")
    rig.check("the pumpkin's seeds were on the ground (collected by walking over them)",
              r["inv"].get("pumpkin_seeds", 0) >= 1, r["inv"])
    rig.frame("s2_pumpkin")
    rig.setblock(bx, by + 1, bz + 3, "air")
    home(0)
    s0 = rig.stats()
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 3, item="flint_and_steel")], label="light the ground")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("flint_and_steel used (use_item +1)", d.get("use_item.flint_and_steel") == 1.0, d)
    rig.fill(bx - 3, by, bz + 1, bx + 3, by + 2, bz + 6, "air")

    # -- throw, bow, eat ---------------------------------------------------------------------
    home(0)
    rig.clear()
    rig.give("snowball", 8)
    rig.give("bow", 1)
    rig.give("arrow", 8)
    rig.give("bread", 2)
    rig.idle(5)
    r = rig.run([P("look_abs", pitch=-10), P("throw", item="snowball", n=2)], label="throw 2")
    rig.check("throw: snowball -2", r["inv"].get("snowball", 0) == 6, r["inv"])
    s0 = rig.stats()
    r = rig.run([P("use_held", item="bow", hold=28)], label="draw the bow")
    d = rig.stat_delta(s0, rig.stats())
    rig.check("bow: arrow -1 and use_item.bow +1",
              r["inv"].get("arrow", 0) == 7 and d.get("use_item.bow") == 1.0, (d, r["inv"]))
    rig.cmd("/difficulty easy")          # peaceful refills the food bar
    rig.cmd("/effect give @a minecraft:hunger 20 40")
    rig.idle(260)
    r = rig.run([P("eat")], label="eat bread")
    rig.check("eat: bread -1", r["inv"].get("bread", 0) == 1, (r["inv"], r["notes"]))
    rig.cmd("/effect clear @a")
    rig.cmd("/difficulty peaceful")

    # -- scan_around ------------------------------------------------------------------------
    home(45)
    r = rig.run([P("scan_around", steps=8)], label="scan_around")
    sheet = next((n.split("tiled into ")[1].split(",")[0] for n in r["notes"]
                  if "tiled into" in n), None)
    p = rig.pos()
    rig.check("scan_around: a contact sheet is written and named in the note",
              bool(sheet) and (rig.agent.memory.root / sheet).exists(), (sheet, r["notes"]))
    rig.check("scan_around: back at the starting yaw", abs(((p["yaw"] - 45) + 180) % 360 - 180) <= 4, p)
    rig.check("scan_around: 8 frames saved", sum(1 for n in r["notes"] if "8 views" in n) == 1, r["notes"])

    # -- bed at night --------------------------------------------------------------------------
    rig.clear()
    rig.give("white_bed", 1)
    rig.cmd("/time set 14000")
    home(0)
    r = rig.run([P("use_at", x=bx, y=by, z=bz + 2, item="white_bed")], label="place the bed")
    rig.check("bed placed (white_bed -1)", r["inv"].get("white_bed", 0) == 0, r["inv"])
    rig.frame("s2_bed_placed")
    r = rig.run([P("sleep_in_bed", x=bx, y=by, z=bz + 2)], label="sleep", max_ticks=400)
    rig.check("sleep_in_bed: the bed was used (position onto the bed or the bed screen)",
              any("sleep_in_bed" in n for n in r["notes"]) and
              (abs(rig.pos()["z"] - (bz + 2.5)) < 1.6 or r["gui"]), (rig.pos(), r["notes"]))
    rig.frame("s2_bed")
    rig.ensure_closed()
    rig.cmd("/time set 1000")


if __name__ == "__main__":
    main_guard(stage)
