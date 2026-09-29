"""Engine probe: is the item-entity selector trustworthy? Summon an ender_eye item and
read it back the same way probe_eye2 looked for a dropped eye."""
from mcu_worldmodel.stages.rig import Rig, SPAWN, scratch_dir

out = scratch_dir("probe_eye3")
rig = Rig(out)


def sticks():
    return rig.inv().get("stick", 0)


def has_eye_item():
    s0 = sticks()
    rig.cmd("/execute if entity @e[type=minecraft:item,nbt={Item:{id:\"minecraft:ender_eye\"}}] run give @a minecraft:stick 1", settle=6)
    return sticks() > s0


def any_item():
    s0 = sticks()
    rig.cmd("/execute if entity @e[type=minecraft:item] run give @a minecraft:stick 1", settle=6)
    return sticks() > s0


try:
    rig.reset()
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 6000")
    x, y, z = SPAWN
    rig.platform(x, y - 1, z, r=8, block="stone", clear_to=8)
    rig.clear(); rig.idle(6)
    print("before: any item", any_item(), "eye item", has_eye_item(), flush=True)
    rig.cmd(f"/summon minecraft:item {x + 4} {y + 1} {z + 4} {{Item:{{id:\"minecraft:ender_eye\",Count:1b}}}}", settle=10)
    print("after summon: any item", any_item(), "eye item", has_eye_item(), flush=True)
    rig.cmd(f"/tp @a {x + 4} {y} {z + 4}", settle=20)
    print("after walking onto it: eyes", rig.inv().get("ender_eye", 0), flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
