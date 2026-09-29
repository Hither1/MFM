"""Engine probe: when (if ever) does a thrown eye become an item entity, and where?
Throw at yaw 0, then every 20 ticks up to 420 read back whether ANY item entity exists
and whether an ender_eye one does; at the first sighting teleport onto the nearest item
and print where it lay relative to the throw spot."""
import math
from mcu_worldmodel.stages.rig import Rig, SPAWN, P, scratch_dir, hotbar_of

out = scratch_dir("probe_eye4")
rig = Rig(out)


def sticks():
    return rig.inv().get("stick", 0)


def exists(sel):
    s0 = sticks()
    rig.cmd(f"/execute if entity {sel} run give @a minecraft:stick 1", settle=4)
    return sticks() > s0


try:
    rig.reset()
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 6000"); rig.cmd("/weather clear")
    x, y, z = SPAWN
    rig.platform(x, y - 1, z, r=30, block="stone", clear_to=20)
    rig.clear(); rig.give("ender_eye", 3); rig.idle(10)
    print("baseline: any item", exists("@e[type=minecraft:item]"), flush=True)
    for k, yaw in enumerate((0.0, 90.0)):
        rig.tp(x, y, z, yaw=yaw, pitch=-12)
        rig.idle(6)
        h = hotbar_of(rig, "ender_eye")
        rig.run([P("equip_hotbar", slot=h or 1)], label="equip", max_ticks=10)
        e0 = rig.inv().get("ender_eye", 0)
        rig._step({**rig.sim.noop_action(), "use": 1})
        found_at = None
        t = 0
        while t < 420:
            for _ in range(20):
                rig._step(rig.sim.noop_action())
            t += 20
            eye_ent = exists("@e[type=minecraft:eye_of_ender]")
            any_item = exists("@e[type=minecraft:item]")
            eye_item = exists("@e[type=minecraft:item,nbt={Item:{id:\"minecraft:ender_eye\"}}]")
            print(f"throw {k} yaw {yaw}: t={t} eye entity {eye_ent} | item any {any_item} | item eye {eye_item}", flush=True)
            if any_item and found_at is None:
                found_at = t
                p0 = rig.pos()
                rig.cmd("/execute at @e[type=minecraft:item,sort=nearest,limit=1] run tp @a ~ ~ ~", settle=16)
                p1 = rig.pos()
                dx, dz = p1["x"] - x, p1["z"] - z
                print(f"   item at dx={dx:+.1f} dz={dz:+.1f} dist={math.hypot(dx, dz):.1f} bearing {math.degrees(math.atan2(-dx, dz)):.0f}; eyes {e0} -> {rig.inv().get('ender_eye', 0)}", flush=True)
                break
        print(f"throw {k}: first item entity at t={found_at}; eyes now {rig.inv().get('ender_eye', 0)}", flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
