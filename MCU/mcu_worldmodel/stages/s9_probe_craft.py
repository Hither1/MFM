"""Probe for stage 9 (not a stage): the blaze_powder craft loses its product when the
rod stack is exactly ONE (stage runs 2/4/5 and probe run 2: craft_item +2, the rod
gone, no powder in any slot, the inventory empty afterwards) and keeps it when the
stack had a remainder to put back (probe run 1: 2 rods -> "+2 blaze_powder, in slot
7"). Three cases from a cleared inventory: one rod, two rods, one rod followed by a
walking sweep (is the product lying on the ground, i.e. did it ride the cursor and
drop at the close?)."""
from __future__ import annotations

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    rig.cmd("/gamerule sendCommandFeedback false")
    rig.cmd("/gamerule doFireTick false")
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 6000")
    rig.platform(x, y - 1, z, r=6, block="stone")
    cases = [("F one rod", 1, False), ("G two rods (a remainder goes back)", 2, False),
             ("H one rod, then a walking sweep", 1, True)]
    for name, rods, sweep in cases:
        rig.tp(x, y, z, yaw=0, pitch=0)
        rig.ensure_closed()
        rig.clear()
        rig.idle(20)                               # let the closed screen's render settle
        rig.give("blaze_rod", rods)
        rig.idle(12)
        s0 = rig.stats()
        r = rig.run([P("open_inventory"), P("craft", item="blaze_powder")], label=name,
                    max_ticks=300)
        rig.idle(30)
        mid = rig.inv()
        rig.frame(f"probe_{name[0]}_open")
        rig.run([P("close_inventory")], label="close", max_ticks=100)
        rig.idle(45)
        after_close = rig.inv()
        if sweep:
            rig.run([RAW(20, forward=1), P("collect_drops", ticks=120), RAW(20, back=1),
                     P("collect_drops", ticks=120)], label="walking sweep", max_ticks=400)
        d = rig.stat_delta(s0, rig.stats())
        got = rig.inv().get("blaze_powder", 0)
        print(f"  [probe] {name}: craft_item +{d.get('craft_item.blaze_powder', 0):g}, "
              f"powder: open {mid.get('blaze_powder', 0)}, after close "
              f"{after_close.get('blaze_powder', 0)}, end {got}; rod left "
              f"{rig.inv().get('blaze_rod', 0)}; notes {[n[:100] for n in r['notes']]}",
              flush=True)
        rig.check(f"{name}: the powder is in the inventory", got >= 1, (d, rig.inv()))


if __name__ == "__main__":
    main_guard(stage)
