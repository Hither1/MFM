"""Stage 13: a level tunnel lights itself.

ob1/ob1b/ob2 (2026-09-06) carried 8+ torches through eleven stretches the ore watch
reported as DARK, planted none, and two were killed by mobs in those tunnels. The
tunnelling tick now pauses every TORCH_EVERY blocks underground, plants a torch on the
floor of the cell it just left, takes the tool back and faces the heading again. This
stage runs one strip_mine through solid stone at y 11 with torches in the hotbar:

1. the torch count falls (a diamond pickaxe tunnels ~8 blocks in 400 ticks on this
   engine, so one torch per call) and the finish note says how many were planted;
2. the tunnel still advances (the pause does not stall the cycle);
3. without torches the same call plants nothing and reports nothing about torches.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import P, SPAWN, Rig, main_guard

Y = 11


def _rock(rig: Rig, bx: int, bz: int) -> None:
    """Solid stone all round a 1x2 starting pocket at Y, so the tunnel is carved."""
    rig.fill(bx - 6, Y - 6, bz - 6, bx + 6, Y + 6, bz + 44, "stone")
    rig.fill(bx, Y, bz, bx, Y + 1, bz + 1, "air")


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    _rock(rig, bx, bz)
    rig.tp(bx + 0.5, Y, bz + 0.5, yaw=0, pitch=8)
    rig.clear()
    rig.give("diamond_pickaxe", 1)
    rig.give("torch", 16)
    rig.idle(20)
    rig.cmd("/replaceitem entity @p hotbar.0 minecraft:diamond_pickaxe")
    rig.idle(10)
    rig.frame("s13_start")
    t0 = rig.inv().get("torch", 0)
    rig.check("setup: 16 torches carried", t0 == 16, rig.inv())

    r = rig.run([P("strip_mine", length=400, ore_watch=False)],
                label="strip_mine(400) with torches", max_ticks=420)
    p = rig.pos()
    t1 = rig.inv().get("torch", 0)
    adv = (p["z"] - (bz + 0.5)) if p else 0.0
    rig.frame("s13_tunnel")
    rig.log(f"advanced {adv:.1f} blocks, torches {t0} -> {t1}, notes {r['notes'][-1:]}")
    rig.check("the tunnel advanced 7+ blocks in 400 ticks (the torch pause did not stall it)",
              adv >= 7.0, (adv, r["notes"]))
    rig.check("a torch left the inventory once 8 blocks were tunnelled",
              t0 - t1 >= 1, (t0, t1, adv))
    rig.check("the finish note counts the torches planted",
              any("torch(es) planted" in n for n in r["notes"]), r["notes"])
    rig.check("the tool is back in hand (strip_mine broke blocks after the torch)",
              r["stats"].get("mine_cycles", 0) >= 6, r["stats"])

    # A second leg without torches: nothing planted, nothing said.
    rig.cmd("/clear @p minecraft:torch")
    rig.idle(10)
    r = rig.run([P("strip_mine", length=200, ore_watch=False)],
                label="strip_mine(200) without torches", max_ticks=220)
    rig.check("no torches: the note says nothing about torches",
              not any("torch" in n for n in r["notes"]), r["notes"])


if __name__ == "__main__":
    main_guard(stage)
