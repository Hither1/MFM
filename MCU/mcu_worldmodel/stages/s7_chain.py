"""Stage 7: one plan that chains a gatherer/opener with the macro that needs its result.

The parser expands a plan against the state BEFORE it runs, so craft(planks) behind a
collect_drops, or place_and_open behind the craft of the table, used to be refused and
dropped (56 of 76 "need Nx" refusals in the 2026-09-03 live arms). Those macros are now
deferred (procedures.DEFERRABLE) and expand when their turn comes; this stage runs both
chains in the engine and reads the inventory.
"""
from mcu_worldmodel.stages.rig import P, Rig, main_guard, SPAWN

def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 1000")
    rig.platform(x, y - 1, z, r=3, block="stone")
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear(); rig.give("oak_log", 3); rig.idle(10)
    # the opener + craft chain is already handled by the parse-time projection (open_inventory
    # marks it open); the deferred path is for INGREDIENTS the earlier entry supplies, and for
    # use_until_gui / place_and_open openers. Here: a log lies on the floor, collect_drops picks
    # it up, then the craft that was short at parse time expands with the log in hand.
    rig.clear(); rig.idle(4)
    rig.cmd(f"/summon minecraft:item {x} {y + 0.5} {z + 2.3} {{Item:{{id:\"minecraft:oak_log\",Count:3b}}}}")
    rig.idle(4)
    r = rig.run([P("collect_drops", ticks=48), P("open_inventory"),
                 P("craft", item="planks", count=2), P("close_inventory")],
                label="collect the log, then craft planks in ONE plan", max_ticks=600)
    rig.check("the craft short of logs at parse time expanded after the pickup (deferred_expanded 1)",
              r["stats"].get("deferred_expanded") == 1, r["stats"])
    rig.check("planks were made (inventory +8 planks from 2 crafts)",
              r["inv"].get("oak_planks", 0) >= 8, r["inv"])
    rig.check("no 'no screen is open' refusal", not any("no screen is open" in n for n in r["notes"]), r["notes"])
    rig.ensure_closed()
    # and a chain whose earlier entry supplies the INGREDIENTS: harvest is too slow here;
    # use place_and_open after a craft of the table in the same plan (needs planks: have 8)
    rig.clear(); rig.give("oak_planks", 12); rig.idle(6)
    r2 = rig.run([P("open_inventory"), P("craft", item="crafting_table"), P("close_inventory"),
                  P("place_and_open", item="crafting_table"), P("craft", item="chest"),
                  P("close_inventory")],
                 label="table crafted, placed and used in ONE plan", max_ticks=900)
    rig.check("place_and_open (refused at parse: no table yet) expanded after the craft",
              r2["stats"].get("deferred_expanded", 0) >= 1, r2["stats"])
    rig.check("a 3x3 recipe crafted in the table that the same plan crafted and placed",
              r2["inv"].get("chest", 0) >= 1, r2["inv"])
    rig.check("place_and_open left a remembered spot for the table",
              "crafting_table" in rig.agent._placed, dict(rig.agent._placed))
    rig.ensure_closed()
    # -- reopen the table from a different heading with use_until_gui(item=): the runner
    # aims at the remembered spot itself (no look_at from the plan).
    p0 = rig.pos()
    r3 = rig.run([P("look_abs", pitch=0, yaw=(p0["yaw"] + 150.0) % 360.0 - 180.0, ticks=25),
                  P("use_until_gui", n=6, item="crafting_table")],
                 label="turn away, then use_until_gui(item=crafting_table)", max_ticks=200)
    rig.check("use_until_gui(item=) re-opened the placed table (table screen up)",
              r3["gui"] and r3["screen"] == "table"
              and r3["stats"].get("use_gui_aimed") == 1, f"gui={r3['gui']} screen={r3['screen']} {r3['stats']}")
    rig.ensure_closed()

if __name__ == "__main__":
    main_guard(stage)
