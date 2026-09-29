"""Stage 16: a zombie in the tunnel behind -- the runner bunkers at the first hit.

ob1b, ob2 and ob4 (2026-09-06) were killed by melee mobs in unlit tunnels: the blind
fightback dealt nothing, the bunker was hit into, the fight macro (stage s15) traded
one swing for 15 hp in the dark. A zombie cannot break blocks, so the reflex on the
second hit underground is now: sprint away along the tunnel, then place two blocks
(feet and head) across it. This stage: an unlit 1x2 tunnel at y 11, difficulty
normal, the avatar mining ahead, a zombie WITH AI summoned 4 blocks behind. It walks
up and hits; within the plan's 400 ticks the wall must stand and the hits must stop.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import P, SPAWN, Rig, main_guard

Y = 11


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty normal")
    rig.cmd("/time set 18000")
    rig.cmd("/gamerule doMobSpawning false")
    rig.fill(bx - 6, Y - 6, bz - 30, bx + 6, Y + 6, bz + 8, "stone")
    rig.fill(bx, Y, bz - 26, bx, Y + 1, bz + 2, "air")            # 1 wide, 2 high, unlit
    rig.clear()
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 16)
    rig.cmd("/effect give @a minecraft:instant_health 1 3", settle=6)
    rig.tp(bx + 0.5, Y, bz + 0.5, yaw=0, pitch=8)               # facing +z, the face
    rig.idle(10)
    rig.summon("zombie", bx + 0.5, Y, bz - 4.5, noai=False)      # behind, toward -z
    rig.idle(5)
    rig.frame("s16_before")
    s0 = rig.stats()
    hp0 = float(rig.info.get("health", 20.0))
    cs0 = dict(rig.agent.cursor_stats)
    # The first hit only interrupts the plan (a turn to face it); the model would plan
    # on, and the second hit inside the melee cadence arms the reflex. Keep mining.
    notes_all: list[str] = []
    for leg in range(5):
        r = rig.run([P("mine_ahead", n=120, ore_watch=False)],
                    label=f"mine ahead, zombie behind (leg {leg + 1})", max_ticks=200)
        notes_all += r["notes"]
        cs_now = rig.agent.cursor_stats
        if (cs_now.get("seal_reflexes", 0) > cs0.get("seal_reflexes", 0)
                or cs_now.get("bunker_capped", 0) > cs0.get("bunker_capped", 0)):
            break
        if float(rig.info.get("health", 0.0)) < 6.0:
            break
    r = {"notes": notes_all}
    d = rig.stat_delta(s0, rig.stats())
    hp1 = float(rig.info.get("health", 0.0))
    p = rig.pos()
    rig.frame("s16_after")
    cs = {k: v - cs0.get(k, 0) for k, v in rig.agent.cursor_stats.items() if v != cs0.get(k, 0)}
    rig.log(f"hp {hp0} -> {hp1} pos {p} delta {d} cursor {cs}")
    for n in r["notes"][-6:]:
        rig.log(f"note: {n[:200]}")
    rig.check("the reflex fired at the first hit: bunker", cs.get("bunker_reflexes", 0) >= 1, cs)
    rig.check("the hole was dug and capped despite the hits", cs.get("bunker_capped", 0) >= 1, cs)
    rig.check("the note says BUNKERED", any("BUNKERED you" in n for n in r["notes"]),
              r["notes"][-3:])
    rig.check("the avatar is alive with 6+ health", hp1 >= 6.0, (hp0, hp1))
    # The hits stop once the wall stands: 150 idle ticks behind it cost no health.
    hp2 = float(rig.info.get("health", 0.0))
    rig.idle(150)
    hp3 = float(rig.info.get("health", 0.0))
    rig.check("no damage in 150 ticks behind the wall", hp3 >= hp2 - 0.5, (hp2, hp3))


if __name__ == "__main__":
    main_guard(stage)
