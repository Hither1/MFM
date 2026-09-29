"""Probe for stage 9 (not a stage): trace explore_nether's walk tick by tick on an open
netherrack platform, and save calibration frames of nether brick, netherrack, lava and
a blaze at several distances. Run like a stage; read the log."""
from __future__ import annotations

import math

import numpy as np

from mcu_worldmodel.stages.rig import SPAWN, P, Rig, main_guard
from mcu_worldmodel.stages.s4_entities import bearing


def stage(rig: Rig) -> None:
    from mcu_worldmodel import macros_nether as MN

    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    rig.cmd("/gamerule sendCommandFeedback false")
    rig.cmd("/gamerule doMobSpawning false")
    rig.cmd("/gamerule doDaylightCycle false")
    rig.cmd("/gamerule doFireTick false")      # lava beside netherrack lit the platform
    rig.cmd("/difficulty easy")
    rig.cmd("/time set 6000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=22, block="netherrack", clear_to=12)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.idle(40)
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 16)
    rig.idle(6)

    # -- trace the walk ---------------------------------------------------------
    trace: list[str] = []
    orig = MN._nexplore_tick

    def traced(agent, st, mk_act):
        pos = agent._cur_pos or {}
        a = orig(agent, st, mk_act)
        keys = {k: v for k, v in (a or {}).items() if v and k != "camera"} if a else None
        cam = (a or {}).get("camera") if a else None
        trace.append(f"t={st['used']} ph={st['phase']} stuck={st['stuck']} "
                     f"pos=({pos.get('x', 0):.2f},{pos.get('y', 0):.2f},{pos.get('z', 0):.2f}) "
                     f"pitch={pos.get('pitch', 0):.0f} lava={st['lava']:.3f} "
                     f"act={keys} cam={cam}")
        return a
    from mcu_worldmodel import macros
    macros.TICKS["_nexplore"] = traced
    r = rig.run([P("explore_nether", axis="z", sign=1, length=20)], label="probe walk",
                max_ticks=400)
    macros.TICKS["_nexplore"] = orig
    for line in trace[:60]:
        print("  [trace]", line, flush=True)
    print("  [trace] ...", len(trace), "ticks; notes:", r["notes"], flush=True)

    # -- calibration frames -----------------------------------------------------
    rig.platform(x, y - 1, z, r=22, block="netherrack", clear_to=12)
    for dist in (6, 12, 22, 35):
        rig.fill(bx - 4, by, bz + dist, bx + 4, by + 5, bz + dist + 1, "nether_bricks")
        rig.tp(x, y, z, yaw=0, pitch=0)
        rig.idle(12)
        rig.frame(f"probe_wall_{dist}")
        rig.fill(bx - 4, by, bz + dist, bx + 4, by + 5, bz + dist + 1, "air")
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.idle(12)
    rig.frame("probe_rack_p0")
    rig.tp(x, y, z, yaw=0, pitch=25)
    rig.idle(12)
    rig.frame("probe_rack_p25")
    for dist, up in ((3.5, 1.5), (7.0, 1.5), (12.0, 2.0)):
        mx, mz = bearing(x, z, 0.0, dist)
        rig.summon("blaze", mx, y + up, mz, noai=True)
        rig.tp(x, y, z, yaw=0, pitch=0)
        rig.idle(16)
        rig.frame(f"probe_blaze_{dist:.0f}")
        rig.cmd("/kill @e[type=!minecraft:player]")
        rig.idle(6)
    rig.fill(bx - 2, by - 1, bz + 3, bx + 2, by - 1, bz + 6, "air")
    rig.fill(bx - 2, by - 2, bz + 3, bx + 2, by - 2, bz + 6, "lava")
    rig.tp(x, y, z, yaw=0, pitch=25)
    rig.idle(16)
    rig.frame("probe_lava_p25")
    rig.tp(x, y, z, yaw=0, pitch=8)
    rig.idle(16)
    rig.frame("probe_lava_p8")
    rig.check("probe ran", True)


if __name__ == "__main__":
    main_guard(stage)
