"""Engine probe: does the standalone sim honour /execute in the_end, end_portal_frame
blockstates, end crystal / ender dragon summons? Prints positions, biome ids, and saves
frames. Run: source ./env.sh; MCU_STAGE_OUT=logs/stages xvfb-run -a <venv>/python probes/probe_end.py"""
import math, sys, time, json
import numpy as np
from mcu_worldmodel.stages.rig import Rig, SPAWN, P, scratch_dir

out = scratch_dir("probe_end")
rig = Rig(out)
try:
    rig.reset()
    def loc():
        ls = rig.info.get("location_stats") or {}
        d = {}
        for k in ("xpos", "ypos", "zpos", "biome_id", "dimension", "yaw", "pitch"):
            v = ls.get(k)
            if v is not None:
                d[k] = float(v.item()) if hasattr(v, "item") else v
        return d
    print("KEYS location_stats:", sorted((rig.info.get("location_stats") or {}).keys()), flush=True)
    print("INFO keys:", sorted(rig.info.keys()), flush=True)
    print("start", loc(), flush=True)
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 1000")
    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    # 1. end portal frame ring with eye=false around a 3x3 pit, 4 blocks ahead
    rig.platform(x, y - 1, z, r=10, block="stone", clear_to=8)
    rig.tp(x, y, z, yaw=0, pitch=0)
    cx, cz = bx, bz + 5          # ring centre (3x3 interior centred here)
    ring = []
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if max(abs(dx), abs(dz)) == 2 and not (abs(dx) == 2 and abs(dz) == 2):
                ring.append((cx + dx, by - 1, cz + dz))
    # facing: frames face the centre of the portal
    for (fx, fy, fz) in ring:
        ddx, ddz = cx - fx, cz - fz
        if abs(ddx) > abs(ddz):
            facing = "east" if ddx > 0 else "west"
        else:
            facing = "south" if ddz > 0 else "north"
        rig.cmd(f"/setblock {fx} {fy} {fz} minecraft:end_portal_frame[eye=false,facing={facing}]", settle=1)
    rig.idle(10)
    rig.frame("p_ring")
    print("ring", ring, flush=True)
    # 2. give eyes, place one via use_at on a frame top
    rig.give("ender_eye", 12)
    rig.idle(6)
    t = ring[0]
    s0 = rig.stats()
    r = rig.run([P("use_at", x=t[0], y=t[1], z=t[2], item="ender_eye", face="above")], label="eye on frame", max_ticks=200)
    print("use_at eye delta", rig.stat_delta(s0, rig.stats()), r["inv"].get("ender_eye"), flush=True)
    rig.frame("p_eye1")
    # 3. fill the rest by command to activate and see the portal
    for (fx, fy, fz) in ring[1:]:
        ddx, ddz = cx - fx, cz - fz
        facing = ("east" if ddx > 0 else "west") if abs(ddx) > abs(ddz) else ("south" if ddz > 0 else "north")
        rig.cmd(f"/setblock {fx} {fy} {fz} minecraft:end_portal_frame[eye=true,facing={facing}]", settle=1)
    rig.idle(20)
    rig.frame("p_ring_full")
    # is there an end_portal block inside?
    inside = (cx, by - 1, cz)
    rig.cmd(f"/execute if block {cx} {by - 1} {cz} minecraft:end_portal run say PORTAL_ACTIVE")
    rig.idle(4)
    print("pos before walking in", rig.pos(), flush=True)
    # 4. walk into the portal
    r = rig.run([P("go_to", x=cx + 0.5, z=cz + 0.5, within=0.4, n=160)], label="walk into portal", max_ticks=300)
    rig.idle(80)
    print("after walk", rig.pos(), loc(), flush=True)
    rig.frame("p_after_walk")
    # 5. explicit execute in the_end
    rig.cmd("/execute in minecraft:the_end run tp @a 100.5 60 0.5 0 0", settle=40)
    print("after execute in the_end", rig.pos(), loc(), flush=True)
    rig.frame("p_end_tp")
    rig.idle(40)
    print("after 40 more", rig.pos(), loc(), flush=True)
    rig.frame("p_end_tp2")
    # 6. crystal + dragon summons
    p = rig.pos() or {}
    rig.cmd(f"/summon minecraft:end_crystal {p.get('x', 100) + 4} {p.get('y', 60) + 1} {p.get('z', 0)}", settle=10)
    rig.frame("p_crystal")
    rig.cmd(f"/summon minecraft:ender_dragon {p.get('x', 100) + 10} {p.get('y', 60) + 6} {p.get('z', 0)}", settle=10)
    rig.frame("p_dragon")
    rig.cmd("/execute if entity @e[type=minecraft:ender_dragon] run say DRAGON_PRESENT")
    rig.idle(20)
    print("end", rig.pos(), loc(), flush=True)
    rig.frame("p_dragon2")
    # 7. back to the overworld
    rig.cmd(f"/execute in minecraft:overworld run tp @a {x} {y} {z} 0 0", settle=40)
    print("back", rig.pos(), loc(), flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
