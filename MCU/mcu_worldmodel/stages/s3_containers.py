"""Stage 3: the container screens against the real GUI.

A chest, a barrel, a double chest, a brewing stand, an enchanting table, a stonecutter
and an anvil are each placed with /setblock, filled with /replaceitem, opened by
look_at + use_until_gui, and driven with the macros in `macros_container.py`. Every
step asserts on `vision.screen_kind`, on the inventory and, where a statistic exists,
on the statistic -- and every open is closed cleanly before the next block.

Engine facts this stage exists to measure (they are recorded in the checks and in
`macros_container`'s module docstring):
  * which container heights the engine draws, and therefore which screen kinds are
    separable at all (chest 168, double chest 222, everything else 166);
  * what `info['inventory']` calls a water bottle and a brewed potion;
  * whether an enchant button click does anything through a GUI click, and what
    observation moves when it does;
  * which stonecutter recipe button produces which block from stone.
"""
from __future__ import annotations

import math
import re

from mcu_worldmodel.stages.rig import P, RAW, SPAWN, Rig, hotbar_of, main_guard, slot_of


def _open(rig: Rig, x: int, y: int, z: int, want: str, label: str) -> dict:
    """Point at the block at (x, y, z) and right-click it open; assert the screen kind."""
    pick = hotbar_of(rig, "iron_pickaxe") or 1
    r = rig.run([P("equip_hotbar", slot=pick),
                 P("look_at", x=x + 0.5, y=y + 0.5, z=z + 0.5),
                 P("use_until_gui", n=6)], label=f"open {label}")
    rig.check(f"{label}: screen open and read as {want!r}",
              r["gui"] and r["screen"] == want, (r["gui"], r["screen"]))
    rig.frame(f"s3_{label}")
    return r


def _close(rig: Rig, label: str) -> dict:
    r = rig.run([P("close_inventory")], label=f"close {label}")
    rig.check(f"{label}: closed cleanly, no refusal",
              not r["gui"] and not any("close refused" in n for n in r["notes"]),
              (r["gui"], r["notes"]))
    if r["gui"]:
        rig.ensure_closed()
    return r


def stage(rig: Rig) -> None:
    from mcu_worldmodel import gui, vision
    import numpy as np

    x, y, z = SPAWN
    bx, by, bz = math.floor(x), int(y), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    rig.cmd("/gamerule doMobSpawning false")
    rig.platform(x, y - 1, z, r=6)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.give("iron_pickaxe", 1)          # a non-placeable item to hold while opening
    rig.idle(10)

    # -- 1. a single chest -----------------------------------------------------
    cx, cy, cz = bx + 2, by, bz
    rig.setblock(cx, cy, cz, "chest")
    rig.cmd(f"/replaceitem block {cx} {cy} {cz} container.0 minecraft:diamond 5")
    rig.cmd(f"/replaceitem block {cx} {cy} {cz} container.4 minecraft:iron_ingot 12")
    rig.cmd(f"/replaceitem block {cx} {cy} {cz} container.13 minecraft:coal 30")
    rig.cmd(f"/replaceitem block {cx} {cy} {cz} container.26 minecraft:gold_ingot 3")
    _open(rig, cx, cy, cz, "chest", "chest")
    grid = rig.agent._grid_line()
    rig.check("chest [GRID] row names the four full cells",
              "chest cells [0,4,13,26]" in grid, grid)
    r = rig.run([P("container_take")], label="container_take (chest)")
    inv = r["inv"]
    rig.check("container_take emptied the chest into the inventory",
              inv.get("diamond", 0) == 5 and inv.get("iron_ingot", 0) == 12
              and inv.get("coal", 0) == 30 and inv.get("gold_ingot", 0) == 3, inv)
    rig.check("container_take says what arrived",
              any("now in the inventory" in n for n in r["notes"]), r["notes"])
    grid = rig.agent._grid_line()
    rig.check("the emptied chest reads 0 of 27 cells full",
              "0 of 27" in grid, grid)
    r = rig.run([P("container_take")], label="container_take (already empty)")
    rig.check("a second take on an empty chest says EMPTY and clicks nothing",
              any("is EMPTY" in n for n in r["notes"]), r["notes"])

    # -- 2. container_put ------------------------------------------------------
    r = rig.run([P("container_put", item="coal")], label="container_put all coal")
    rig.check("all the coal went into the chest",
              r["inv"].get("coal", 0) == 0
              and any("moved into the chest" in n for n in r["notes"]),
              (r["inv"].get("coal"), r["notes"]))
    r = rig.run([P("container_put", item="iron_ingot", n=4)], label="container_put n=4")
    rig.check("a partial put moved exactly 4 iron_ingot",
              r["inv"].get("iron_ingot", 0) == 8, r["inv"].get("iron_ingot"))
    _close(rig, "chest")

    # -- 3. a barrel reads as the same 3-row screen ----------------------------
    rig.setblock(cx, cy + 1, cz, "air")
    px, py, pz = bx - 2, by, bz
    rig.setblock(px, py, pz, "barrel")
    rig.cmd(f"/replaceitem block {px} {py} {pz} container.8 minecraft:redstone 7")
    _open(rig, px, py, pz, "chest", "barrel")
    r = rig.run([P("container_take")], label="container_take (barrel)")
    rig.check("the barrel's redstone arrived", r["inv"].get("redstone", 0) == 7, r["inv"])
    _close(rig, "barrel")

    # -- 4. a double chest is a taller screen ----------------------------------
    dx, dz = bx, bz + 2
    rig.setblock(dx, by, dz, "chest[facing=north,type=left]")
    rig.setblock(dx + 1, by, dz, "chest[facing=north,type=right]")
    rig.idle(6)
    r = rig.run([P("equip_hotbar", slot=hotbar_of(rig, "iron_pickaxe") or 1),
                 P("look_at", x=dx + 0.5, y=by + 0.5, z=dz + 0.5),
                 P("use_until_gui", n=6)], label="open double chest")
    if r["screen"] != "chest2":
        # /setblock does not connect chests by itself in every orientation; the other
        # half-pairing is the one that does.
        rig.ensure_closed()
        rig.setblock(dx, by, dz, "chest[facing=north,type=right]")
        rig.setblock(dx + 1, by, dz, "chest[facing=north,type=left]")
        rig.idle(6)
        r = rig.run([P("look_at", x=dx + 0.5, y=by + 0.5, z=dz + 0.5),
                     P("use_until_gui", n=6)], label="open double chest (swapped)")
    rig.check("a double chest reads as 'chest2' (176x222, six rows)",
              r["gui"] and r["screen"] == "chest2", (r["gui"], r["screen"]))
    rig.frame("s3_double_chest")
    if r["screen"] == "chest2":
        f = np.asarray(rig.info["pov"])
        ox, oy = gui.container_origin()
        lum = f.astype(np.float32).mean(-1)
        rig.check("the double chest's player hotbar is drawn 27px lower (169, not 142)",
                  vision._is_slot(lum, int(ox + gui.player_slot_topleft(0, "chest2")[0]),
                                  int(oy + gui.player_slot_topleft(0, "chest2")[1]))
                  and not vision._is_slot(lum, int(ox + gui.slot_topleft(0)[0]),
                                          int(oy + gui.slot_topleft(0)[1])))
        # Each half of a double chest is its own block entity with its own container.0-26;
        # `container.50` on one block does nothing (measured, run 1). The screen shows one
        # half's 27 cells above the other's, so this lands in a row the single-chest
        # geometry could never reach.
        rig.cmd(f"/replaceitem block {dx + 1} {by} {dz} container.20 minecraft:emerald 9")
        rig.idle(6)
        r = rig.run([P("container_take", max_stacks=54)], label="container_take (double)")
        rig.check("a cell in the double chest's SECOND half was reachable",
                  r["inv"].get("emerald", 0) == 9, r["inv"].get("emerald"))
    _close(rig, "double chest")

    # -- 5. brewing: water bottles -> awkward -> fire resistance ---------------
    rig.ensure_closed()
    sx, sy, sz = bx, by, bz - 3
    rig.setblock(sx, sy, sz, "brewing_stand")
    rig.cmd('/give @a minecraft:potion{Potion:"minecraft:water"} 1')
    rig.cmd('/give @a minecraft:potion{Potion:"minecraft:water"} 1')
    rig.cmd('/give @a minecraft:potion{Potion:"minecraft:water"} 1')
    rig.give("nether_wart", 1)
    rig.give("magma_cream", 1)
    rig.give("blaze_powder", 2)
    rig.idle(8)
    bottle_name = next((k for k in rig.inv() if "potion" in k or "bottle" in k), None)
    rig.log(f"ENGINE FACT: a water bottle is reported in the inventory as "
            f"{bottle_name!r} x{rig.inv().get(bottle_name or '', 0)}")
    rig.check("the engine names a water bottle in the inventory at all",
              bottle_name is not None, sorted(rig.inv()))
    _open(rig, sx, sy, sz, "brewing", "brewing_stand")
    r = rig.run([P("brew", ingredient="nether_wart", bottles=3)], label="brew 1")
    rig.check("brew 1: the nether_wart left the inventory",
              r["inv"].get("nether_wart", 0) == 0, r["inv"].get("nether_wart"))
    rig.check("brew 1: the note says 400 ticks and does not wait",
              any("400 ticks" in n for n in r["notes"]), r["notes"])
    grid = rig.agent._grid_line()
    rig.check("brewing [GRID] row shows the loaded cells", "brewing [" in grid, grid)
    rig.idle(430)
    r = rig.run([P("brew", ingredient="magma_cream", bottles=0)], label="brew 2")
    rig.check("brew 2: the magma_cream left the inventory",
              r["inv"].get("magma_cream", 0) == 0, r["inv"].get("magma_cream"))
    rig.idle(430)
    before = rig.inv().get(bottle_name or "potion", 0)
    r = rig.run([P("brew_take")], label="brew_take")
    got = r["inv"].get(bottle_name or "potion", 0)
    rig.check("brew_take brought three potions back", got - before == 3, (before, got))
    rig.log(f"ENGINE FACT: after two brews the inventory reports {got} x "
            f"{bottle_name!r} -- no NBT, so fire resistance is indistinguishable from "
            f"water in the observation")
    _close(rig, "brewing_stand")

    # -- 6. enchanting ---------------------------------------------------------
    rig.ensure_closed()
    ex, ey, ez = bx - 3, by, bz - 3
    rig.setblock(ex, ey, ez, "enchanting_table")
    rig.cmd("/xp add @a 30 levels")
    rig.give("diamond_sword", 1)
    rig.give("lapis_lazuli", 6)
    rig.idle(8)
    _open(rig, ex, ey, ez, "enchanting", "enchanting_table")
    lap0 = rig.inv().get("lapis_lazuli", 0)
    r = rig.run([P("enchant", item="diamond_sword", option=1)], label="enchant")
    lap1 = r["inv"].get("lapis_lazuli", 0)
    rig.log(f"ENGINE FACT: enchant option 1 -- lapis {lap0} -> {lap1}, "
            f"diamond_sword x{r['inv'].get('diamond_sword', 0)}, notes {r['notes']}")
    rig.check("the enchant button fired and cost lapis, or the macro says why not",
              lap1 < lap0 or any("changed NOTHING" in n for n in r["notes"]),
              (lap0, lap1, r["notes"]))
    rig.check("the sword came back out of the enchanting slot",
              r["inv"].get("diamond_sword", 0) == 1, r["inv"].get("diamond_sword"))
    _close(rig, "enchanting_table")

    # -- 7. stonecutting -------------------------------------------------------
    rig.ensure_closed()
    tx, ty, tz = bx + 3, by, bz - 3
    rig.setblock(tx, ty, tz, "stonecutter")
    rig.give("stone", 16)
    rig.idle(8)
    _open(rig, tx, ty, tz, "stonecutter", "stonecutter")
    grid = rig.agent._grid_line()
    rig.check("stonecutter [GRID] row counts the recipe buttons offered",
              "recipe button" in grid, grid)
    # ENGINE FACT (run 1, 2026-09-03): from `stone` this stonecutter offers, in button
    # order, chiseled_stone_bricks, stone_brick_slab, stone_brick_stairs,
    # stone_brick_wall -- plain `stone_bricks` is NOT among them (that is the 2x2
    # crafting recipe). The search is asked for one of the recipes that does exist.
    r = rig.run([P("stonecut", item="stone", output="stone_brick_stairs", tries=4)],
                label="stonecut search stone -> stone_brick_stairs")
    rig.log(f"ENGINE FACT: stonecut search notes -- {r['notes']}")
    rig.check("the search produced stone_brick_stairs",
              r["inv"].get("stone_brick_stairs", 0) >= 1, r["inv"])
    rig.check("the search cut ONE item per button (the stack is nearly intact)",
              r["inv"].get("stone", 0) >= 12, r["inv"].get("stone"))
    found = None
    for n in r["notes"]:
        m = re.search(r"button=(\d+)", n)
        if m:
            found = int(m.group(1))
    rig.log(f"ENGINE FACT: stone -> stone_brick_stairs is stonecutter button {found}")
    rig.check("the note names the button to reuse", found is not None, r["notes"])
    if found is not None:
        stone0 = rig.inv().get("stone", 0)
        cut0 = rig.inv().get("stone_brick_stairs", 0)
        r = rig.run([P("stonecut", item="stone", output="stone_brick_stairs",
                       button=found)],
                    label=f"stonecut whole stack with button {found}")
        rig.check("with a known button the whole stack is cut in one call",
                  r["inv"].get("stone", 0) == 0
                  and r["inv"].get("stone_brick_stairs", 0) > cut0, (stone0, cut0, r["inv"]))
    _close(rig, "stonecutter")

    # -- 8. an anvil is recognised, and nothing is registered for it -----------
    rig.ensure_closed()
    ax, ay, az = bx + 3, by, bz + 1
    rig.setblock(ax, ay, az, "anvil")
    rig.idle(6)
    _open(rig, ax, ay, az, "anvil", "anvil")
    _close(rig, "anvil")

    # -- 9. the wrong screen is refused, not clicked through -------------------
    rig.ensure_closed()
    rig.give("nether_wart", 1)
    _open(rig, cx, cy, cz, "chest", "chest_again")
    r = rig.run([P("brew", ingredient="nether_wart")], label="brew on a chest screen")
    rig.check("brew on a chest screen is refused with a note naming both screens",
              any("needs the brewing screen" in n for n in r["notes"]), r["notes"])
    rig.check("nothing was clicked through the refusal",
              r["inv"].get("nether_wart", 0) == 1, r["inv"].get("nether_wart"))
    _close(rig, "chest_again")
    rig.frame("s3_end")


if __name__ == "__main__":
    main_guard(stage)
