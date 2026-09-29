"""Engine probe: where does a thrown eye of ender actually land? Throw, wait, then find
the ender_eye item entity with a selector and teleport onto it."""
import math
from mcu_worldmodel.stages.rig import Rig, SPAWN, P, scratch_dir, hotbar_of

out = scratch_dir("probe_eye2")
rig = Rig(out)


def sticks():
    return rig.inv().get("stick", 0)


def has_eye_item(radius=None):
    s0 = sticks()
    sel = "@e[type=minecraft:item,nbt={Item:{id:\"minecraft:ender_eye\"}}" + (f",distance=..{radius}" if radius else "") + "]"
    rig.cmd(f"/execute if entity {sel} run give @a minecraft:stick 1", settle=6)
    return sticks() > s0


try:
    rig.reset()
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 6000"); rig.cmd("/weather clear")
    x, y, z = SPAWN
    rig.platform(x, y - 1, z, r=24, block="stone", clear_to=14)
    rig.clear(); rig.give("ender_eye", 4); rig.idle(10)
    for k, yaw in enumerate((0.0, 0.0, 90.0)):
        rig.tp(x, y, z, yaw=yaw, pitch=-12)
        rig.idle(6)
        h = hotbar_of(rig, "ender_eye")
        rig.run([P("equip_hotbar", slot=h or 1)], label="equip", max_ticks=10)
        e0 = rig.inv().get("ender_eye", 0)
        rig._step({**rig.sim.noop_action(), "use": 1})
        for t in range(1, 141):
            rig._step(rig.sim.noop_action())
            if t in (60, 85, 100, 115, 130, 140):
                print(f"throw {k} yaw {yaw}: t={t} eye item exists: {has_eye_item()} within 20: {has_eye_item(20)}", flush=True)
        p0 = rig.pos()
        rig.cmd("/execute at @e[type=minecraft:item,nbt={Item:{id:\"minecraft:ender_eye\"}},limit=1] run tp @a ~ ~1 ~", settle=16)
        p1 = rig.pos()
        print(f"throw {k} yaw {yaw}: eyes {e0} -> {rig.inv().get('ender_eye', 0)}; tp {p0} -> {p1}; "
              f"offset from throw spot dx={p1['x'] - x:+.1f} dz={p1['z'] - z:+.1f} "
              f"(bearing of offset {math.degrees(math.atan2(-(p1['x'] - x), p1['z'] - z)):.0f})", flush=True)
        rig.idle(20)
        print(f"   after 20 more ticks eyes {rig.inv().get('ender_eye', 0)}", flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
