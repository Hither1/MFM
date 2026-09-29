"""Engine probe: what a thrown eye of ender looks like in the frames, tick by tick."""
import math
from mcu_worldmodel.stages.rig import Rig, SPAWN, P, scratch_dir, hotbar_of

out = scratch_dir("probe_eye")
rig = Rig(out)
try:
    rig.reset()
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 6000"); rig.cmd("/weather clear")
    x, y, z = SPAWN
    rig.platform(x, y - 1, z, r=14, block="stone", clear_to=12)
    rig.tp(x, y, z, yaw=0, pitch=-12)
    rig.clear(); rig.give("ender_eye", 6); rig.idle(10)
    for yaw in (0.0, 180.0):
        rig.tp(x, y, z, yaw=yaw, pitch=-12)
        rig.idle(6)
        h = hotbar_of(rig, "ender_eye")
        rig.run([P("equip_hotbar", slot=h or 1)], label="equip", max_ticks=10)
        rig.frame(f"eye_y{yaw:.0f}_before")
        print(f"yaw {yaw}: eyes before", rig.inv().get("ender_eye"), rig.pos(), flush=True)
        rig._step({**rig.sim.noop_action(), "use": 1})
        for t in range(1, 121):
            rig._step(rig.sim.noop_action())
            if (t <= 40 and t % 3 == 0) or t % 15 == 0:
                rig.frame(f"eye_y{yaw:.0f}_t{t:03d}")
        print(f"yaw {yaw}: eyes after 120 ticks", rig.inv().get("ender_eye"), rig.pos(), flush=True)
        # sweep the drop along the facing: walk 12 blocks ahead
        dx, dz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        r = rig.run([P("go_to", x=x + dx * 12, z=z + dz * 12, within=1.0, n=160),
                     P("collect_drops", ticks=80)], label="walk + sweep", max_ticks=300)
        print(f"yaw {yaw}: eyes after sweep", rig.inv().get("ender_eye"), rig.pos(), flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
