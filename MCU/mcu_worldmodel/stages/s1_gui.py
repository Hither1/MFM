"""Stage 1: the GUI macros against the real screens.

From four logs: planks x2, sticks, a table (2x2 in the survival inventory); place and
open the table; a wooden pickaxe; a furnace and a stone pickaxe (3x3); place and open
the furnace; load three iron ore with coal, wait, take the ingots; a second table for
a bucket and an iron pickaxe; then flint out of a gravel bank with mine_until.
Every craft is checked on the inventory and the craft_item statistic; every open on
isGuiOpen and the screen kind the frame shows.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import SPAWN, Rig, main_guard


def P(name: str, **args):
    return {"procedure": name, "args": args}


def slot_of(rig: Rig, item: str) -> int | None:
    inv = rig.info.get("inventory") or {}
    for s in range(36):
        e = inv.get(s) or inv.get(str(s))
        if isinstance(e, dict) and str(e.get("type")) == item:
            return s
    return None


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=5)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.idle(10)

    # -- 2x2: planks, sticks, table -------------------------------------------
    rig.give("oak_log", 4)
    r = rig.run([P("open_inventory"), P("craft", item="planks", count=2)], label="planks x2")
    rig.check("planks x2 -> 8 planks", r["inv"].get("oak_planks", 0) == 8, r["inv"])
    rig.check("craft note reports the product",
              any("craft(planks)" in n and "crafted" in n for n in r["notes"]), r["notes"])
    r = rig.run([P("craft", item="stick")], label="sticks")
    rig.check("sticks -> 4", r["inv"].get("stick", 0) == 4, r["inv"])
    r = rig.run([P("craft", item="crafting_table"), P("close_inventory")], label="table")
    rig.check("crafting_table crafted", r["inv"].get("crafting_table", 0) == 1, r["inv"])
    rig.check("screen closed cleanly", not r["gui"], r)
    rig.check("craft_item statistic moved", rig.stat("craft_item", "crafting_table") >= 1)
    rig.frame("s1_after_2x2")

    # -- place and open the table ----------------------------------------------
    rig.ensure_closed()
    if rig.inv().get("crafting_table", 0) == 0:
        rig.give("crafting_table", 1)
    r = rig.run([P("place_and_open", item="crafting_table")], label="place table")
    rig.check("table placed (use_item)", rig.stat("use_item", "crafting_table") >= 1)
    rig.check("table screen open", r["gui"] and r["screen"] == "table", r)
    rig.frame("s1_table_open")
    rig.give("oak_planks", 2)
    r = rig.run([P("craft", item="wooden_pickaxe")], label="wooden pickaxe")
    rig.check("wooden_pickaxe crafted", r["inv"].get("wooden_pickaxe", 0) == 1, r["inv"])
    s = slot_of(rig, "wooden_pickaxe")
    rig.check("the pickaxe went to the hotbar", s is not None and s <= 8, s)
    rig.give("cobblestone", 11)
    r = rig.run([P("craft", item="furnace"), P("craft", item="stone_pickaxe"),
                 P("close_inventory")], label="furnace + stone pickaxe")
    rig.check("furnace crafted", r["inv"].get("furnace", 0) == 1, r["inv"])
    rig.check("stone_pickaxe crafted", r["inv"].get("stone_pickaxe", 0) == 1, r["inv"])
    rig.check("furnace and pickaxe took <= 450 ticks", r["ticks"] <= 450, r["ticks"])

    # -- furnace: place, load, wait, take -----------------------------------------
    rig.ensure_closed()
    if rig.inv().get("furnace", 0) == 0:
        rig.give("furnace", 1)
    r = rig.run([P("look_abs", yaw=90), P("place_and_open", item="furnace")],
                label="place furnace")
    rig.check("furnace placed", rig.stat("use_item", "furnace") >= 1)
    rig.check("furnace screen open", r["gui"] and r["screen"] == "furnace", r)
    rig.frame("s1_furnace_open")
    rig.give("iron_ore", 3)
    rig.give("coal", 2)
    r = rig.run([P("furnace_load", item="iron_ore", fuel="auto")], label="furnace_load")
    rig.check("ore left the inventory", r["inv"].get("iron_ore", 0) == 0, r["inv"])
    rig.check("one coal used as fuel", r["inv"].get("coal", 0) == 1, r["inv"])
    rig.check("load note confirms both cells",
              any("in the smelt cell" in n for n in r["notes"]), r["notes"])
    rig.frame("s1_furnace_loaded")
    r = rig.run([P("furnace_take", item="iron_ingot")], label="furnace_take (too early)")
    rig.check("an early take stops on the empty output cell",
              any("output cell is EMPTY" in n for n in r["notes"])
              or r["inv"].get("iron_ingot", 0) >= 1, r["notes"])
    rig.idle(640)
    r = rig.run([P("furnace_take", item="iron_ingot")], label="furnace_take")
    rig.check("three ingots taken", r["inv"].get("iron_ingot", 0) == 3, r["inv"])
    # Engine fact (2026-09-03): furnace output counts as craft_item, never pickup --
    # `pickup` is items picked up off the ground. A `pickup iron_ingot` milestone needs
    # drop_and_pickup afterwards.
    rig.check("furnace output counts as craft_item iron_ingot",
              rig.stat("craft_item", "iron_ingot") >= 3 and rig.stat("pickup", "iron_ingot") == 0,
              (rig.stat("craft_item", "iron_ingot"), rig.stat("pickup", "iron_ingot")))
    rig.frame("s1_after_take")
    r = rig.run([P("close_inventory")], label="close furnace")
    rig.check("furnace screen closed", not r["gui"], r)
    ingot_slot = slot_of(rig, "iron_ingot")
    r = rig.run([P("drop_and_pickup", slot=ingot_slot)], label="drop_and_pickup ingots")
    rig.check("drop_and_pickup: the ingots are back and pickup moved",
              r["inv"].get("iron_ingot", 0) == 3 and rig.stat("pickup", "iron_ingot") >= 3
              and not r["gui"],
              (r["inv"].get("iron_ingot"), rig.stat("pickup", "iron_ingot"), r["notes"]))

    # -- 3x3 again: bucket + iron pickaxe ----------------------------------------
    rig.ensure_closed()
    rig.give("iron_ingot", 3)
    rig.give("stick", 2)              # the wooden and stone pickaxes used the first 4
    rig.give("crafting_table", 1)
    r = rig.run([P("look_abs", yaw=180), P("place_and_open", item="crafting_table"),
                 P("craft", item="bucket"), P("craft", item="iron_pickaxe"),
                 P("close_inventory")], label="bucket + iron pickaxe")
    rig.check("bucket crafted", r["inv"].get("bucket", 0) == 1, r["inv"])
    rig.check("iron_pickaxe crafted", r["inv"].get("iron_pickaxe", 0) == 1, r["inv"])
    rig.check("sticks consumed as expected", r["inv"].get("stick", 0) == 0, r["inv"])

    # -- a wrong screen is refused, not clicked through ----------------------------
    rig.ensure_closed()
    rig.give("stick", 2)
    rig.give("cobblestone", 2)
    rig.idle(5)
    r = rig.run([P("open_inventory"), P("craft", item="stone_sword"),
                 P("close_inventory")], label="3x3 recipe on the 2x2 screen")
    rig.check("a 3x3 recipe on the survival screen is refused",
              any("needs the table screen" in n for n in r["notes"]), r["notes"])
    rig.check("no stone_sword appeared", r["inv"].get("stone_sword", 0) == 0)
    if r["gui"]:
        rig.run([P("close_inventory")], label="close after refusal")

    # -- mine_until: flint out of gravel -----------------------------------------
    rig.ensure_closed()
    x0, z0 = int(x // 1), int(z // 1)
    rig.cmd(f"/fill {x0 + 2} {int(y)} {z0 - 1} {x0 + 3} {int(y) + 3} {z0 + 1} minecraft:gravel")
    pick = slot_of(rig, "iron_pickaxe")
    plan = [P("equip_hotbar", slot=(pick + 1) if pick is not None and pick <= 8 else 1),
            P("look_abs", pitch=8, yaw=-90), P("mine_until", item="flint", n=1, ticks=380)]
    r = rig.run(plan, label="mine_until flint")
    gravel = rig.stat("mine_block", "gravel")
    rig.check("gravel was mined", gravel >= 1, gravel)
    got = r["inv"].get("flint", 0) >= 1
    rig.check("flint arrived and the macro stopped early, or the budget ran out honestly",
              (got and any("stopped early" in n for n in r["notes"])) or (not got),
              (got, r["notes"]))
    rig.log(f"flint={r['inv'].get('flint', 0)} gravel mined={gravel:g} ticks={r['ticks']}")
    rig.frame("s1_end")


if __name__ == "__main__":
    main_guard(stage)
