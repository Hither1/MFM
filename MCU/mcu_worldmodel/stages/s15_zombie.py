"""Stage 15: the fight macro against a LIVE zombie in a dark tunnel.

Three of the four 2026-09-06 relay runs (ob1b, ob2, ob4) were killed by melee mobs in
unlit tunnels; the runner's fightback reflex swings blind (3 reflexes in the corpus,
0 damage dealt). The `fight` macro tracks a mob by colour and motion, but stage s4
only proved it on a NoAI zombie in daylight. This stage: an unlit stone tunnel at y
11, difficulty normal, a zombie WITH AI summoned 4 blocks ahead, a diamond sword,
fight(ticks=300) -- does it land hits and kill? Then the same with the zombie behind
the avatar (the shove case) after a 180-degree turn. Two summons, two fights.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import P, SPAWN, Rig, main_guard

Y = 11


def _tunnel(rig: Rig, bx: int, bz: int) -> None:
    rig.fill(bx - 6, Y - 6, bz - 12, bx + 6, Y + 6, bz + 14, "stone")
    rig.fill(bx, Y, bz - 8, bx, Y + 1, bz + 10, "air")          # 1 wide, 2 high, unlit


def _fight(rig: Rig, label: str, zx: float, zz: float, yaw: float) -> dict:
    rig.cmd("/kill @e[type=minecraft:zombie]")
    rig.cmd("/effect give @a minecraft:instant_health 1 3", settle=6)
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.tp(bx + 0.5, Y, bz + 0.5, yaw=yaw, pitch=0)
    rig.idle(10)
    rig.summon("zombie", zx, Y, zz, noai=False)
    rig.idle(10)
    rig.frame(f"s15_{label}_before")
    s0 = rig.stats()
    hp0 = float(rig.info.get("health", 20.0))
    r = rig.run([P("fight", ticks=300, label="zombie")], label=f"fight {label}",
                max_ticks=420)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame(f"s15_{label}_after")
    hp1 = float(rig.info.get("health", 0.0))
    rig.log(f"{label}: delta {d} hp {hp0} -> {hp1} notes {[n[:120] for n in r['notes'][-2:]]}")
    rig.check(f"{label}: the swings landed (damage_dealt moved)",
              d.get("custom.damage_dealt", 0) > 0, d)
    rig.check(f"{label}: kill_entity.zombie +1", d.get("kill_entity.zombie", 0) >= 1.0, d)
    rig.check(f"{label}: the avatar survived with 8+ health", hp1 >= 8.0, (hp0, hp1))
    return d


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty normal")
    rig.cmd("/time set 18000")
    rig.cmd("/gamerule doMobSpawning false")
    _tunnel(rig, bx, bz)
    rig.clear()
    rig.give("diamond_sword", 1)
    rig.give("cobblestone", 16)
    rig.idle(10)
    # 1. ahead in the dark, 4 blocks
    _fight(rig, "ahead", bx + 0.5, bz + 4.5, yaw=0)
    # 2. behind: the zombie is summoned at the avatar's back, the macro must find it
    _fight(rig, "behind", bx + 0.5, bz - 4.5, yaw=0)


if __name__ == "__main__":
    main_guard(stage)
