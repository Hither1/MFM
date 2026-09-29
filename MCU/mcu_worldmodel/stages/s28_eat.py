"""Stage 28: the starving example eats what you carry (gen 4, 2026-09-10).

skills/reflexes/scripts/starving.py, copied into mine/reflexes/ as the model does in its
first turn, runs every 4 ticks on the live state. With mutton in a MAIN inventory slot
(not the hotbar) and the food bar dropping a point below 18 during a plan, it must fire
once, drop the plan and run the built-in `eat`: mutton -1, the bar back up, one
[REFLEX starving] note naming the food. With nothing to eat, the crossing below 18
during a plan is one note and no stop (the plan runs on); a further point lost is
nothing. While the eat itself runs (`entry == "eat"`) the reflex stays quiet. Hunger is driven by the hunger effect (difficulty easy: peaceful never drains).
"""
from __future__ import annotations

import shutil

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 80, -5560


def _food(rig: Rig) -> float:
    v = rig.info.get("food_level")
    return float(v.item()) if hasattr(v, "item") else float(v)


def _drain_to(rig: Rig, target: int, max_ticks: int = 600) -> None:
    """Hunger effect at a high amplifier until the bar reads `target`, then clear it."""
    rig.cmd("/effect give @s minecraft:hunger 60 100", settle=1)
    t = 0
    while _food(rig) > target and t < max_ticks:
        rig.idle(1)
        t += 1
    rig.cmd("/effect clear @s", settle=2)
    rig.log(f"drained to food {_food(rig):.0f} in {t} ticks")


def stage(rig: Rig) -> None:
    from mcu_worldmodel import skills

    rig.cmd("/difficulty easy")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    rig.fill(X - 8, Y - 6, Z - 8, X + 8, Y, Z + 8, "stone")
    rig.fill(X - 8, Y + 1, Z - 8, X + 8, Y + 6, Z + 8, "air")
    rig.fill(X - 8, Y + 7, Z - 8, X + 8, Y + 7, Z + 8, "stone")       # a roof: no mob drops in
    for xx in range(X - 7, X + 8, 4):
        rig.fill(xx, Y + 5, Z - 7, xx, Y + 5, Z + 7, "glowstone")
    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=20)
    rig.clear()
    rig.idle(10)

    a = rig.agent
    a.own, a.own_reflexes, a.reflexes, a.skills = True, True, False, True
    a.memory.own = True
    skills.write_skills(a.memory.root)
    rd = a.memory.root / "mine" / "reflexes"
    rd.mkdir(parents=True, exist_ok=True)
    (a.memory.root / "mine" / "procedures").mkdir(parents=True, exist_ok=True)
    shutil.copy(a.memory.root / "skills" / "reflexes" / "scripts" / "starving.py", rd / "starving.py")

    # --- 1. food carried in a main inventory slot: the drop below 18 eats -------------
    rig.cmd("/replaceitem entity @s hotbar.0 minecraft:cobblestone 16")
    rig.cmd("/replaceitem entity @s inventory.3 minecraft:mutton 3")   # main inventory, not the hotbar
    rig.idle(20)
    inv0 = rig.inv()
    rig.check("mutton x3 is carried (main inventory)", inv0.get("mutton") == 3, inv0)
    _drain_to(rig, 18)
    f0 = _food(rig)
    rig.check("the bar sits at 18 before the plan", f0 == 18.0, f0)
    rig.cmd("/effect give @s minecraft:hunger 30 30", settle=1)        # ~a point per 26 ticks
    r = rig.run([P("watch", n=240)], label="a 240-tick watch while the bar drops below 18", max_ticks=600)
    rig.cmd("/effect clear @s")
    rig.idle(20)
    fires = [n for n in r["notes"] if n.startswith("[REFLEX starving] food")]   # the firing, not the eat's own notes
    rig.check("the reflex fired once, named the mutton and dropped the plan",
              len(fires) == 1 and "with mutton carried: eating" in fires[0]
              and "dropped the rest of your plan" in fires[0]
              and "running the reflex's own actions" in fires[0], r["notes"])
    rig.check("the plan was cut well short of its 240 ticks by the eat", r["ticks"] < 200, r["ticks"])
    inv1 = rig.inv()
    rig.check("one mutton eaten (3 -> 2)", inv1.get("mutton") == 2, inv1)
    rig.check("the eat completed (raw mutton: +2 food, so the bar itself is no check)",
              any("eat(mutton): use_item +1, mutton -1" in n for n in r["notes"]), r["notes"])
    rig.check("stats: exactly one own-reflex fire", a.cursor_stats.get("own_reflex_fires") == 1,
              dict(a.cursor_stats))
    rig.frame("s28_after_eat")

    # --- 2. nothing to eat: the crossing is one note, no stop; a further point is silent --
    rig.ensure_closed()
    rig.clear()
    rig.cmd("/replaceitem entity @s hotbar.0 minecraft:cobblestone 16")
    rig.cmd("/effect give @s minecraft:saturation 1 9", settle=20)      # instant: +10 food, capped at 20
    rig.check("the bar is full again before the second drain", _food(rig) == 20.0, _food(rig))
    _drain_to(rig, 18)
    f2 = _food(rig)
    rig.check("the bar sits at 18 again, nothing to eat", f2 == 18.0 and not rig.inv().get("mutton"), (f2, rig.inv()))
    rig.cmd("/effect give @s minecraft:hunger 30 30", settle=1)
    r2 = rig.run([P("watch", n=160)], label="a 160-tick watch, no food, the bar crossing 18 then 17", max_ticks=400)
    rig.cmd("/effect clear @s")
    notes2 = [n for n in r2["notes"] if n.startswith("[REFLEX starving] food")]
    rig.check("one note at the crossing: nothing to eat, no stop, the plan ran on",
              len(notes2) == 1 and "nothing to eat" in notes2[0]
              and "dropped the rest of your plan" not in notes2[0]
              and r2["ticks"] >= 150, (notes2, r2["ticks"]))
    f3 = _food(rig)
    rig.check("the bar kept falling past the crossing (the note did not repeat)", f3 <= 16.0, f3)   # 160 ticks at ~26/point
    rig.check("stats: two fires in all", a.cursor_stats.get("own_reflex_fires") == 2, dict(a.cursor_stats))


if __name__ == "__main__":
    main_guard(stage)
