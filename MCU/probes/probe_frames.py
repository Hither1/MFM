"""Engine probe: what an End portal frame's top looks like with and without an eye, seen
from the standing spot one block outside it (crosshair on the top-face centre; the pose
is set by /tp so no plan repeats and the governor stays quiet)."""
import math
import numpy as np
from mcu_worldmodel.stages.rig import Rig, SPAWN, scratch_dir
from mcu_worldmodel import macros_world as MW

out = scratch_dir("probe_frames")
rig = Rig(out)
try:
    rig.reset()
    rig.cmd("/difficulty peaceful"); rig.cmd("/time set 6000"); rig.cmd("/weather clear")
    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    rig.platform(x, y - 1, z, r=12, block="stone_bricks", clear_to=10)
    fx, fy, fz = bx, by - 1, bz + 4          # one frame, sunk flush with the floor
    top = (fx + 0.5, fy + 0.81, fz + 0.5)
    for eye in ("false", "true"):
        rig.cmd(f"/setblock {fx} {fy} {fz} minecraft:end_portal_frame[eye={eye},facing=south]")
        for dist, label in ((1, "d1"), (2, "d2"), (3, "d3")):
            px, pz = fx + 0.5, fz - dist + 0.5
            pos = {"x": px, "y": float(by), "z": pz, "pitch": 0.0, "yaw": 0.0}
            pitch, yaw, d = MW.angles_to(pos, top)
            rig.tp(px, by, pz, yaw=yaw, pitch=pitch)
            rig.idle(8)
            rig.frame(f"frame_{eye}_{label}")
            pov = np.asarray(rig.info["pov"]).astype(np.float32)
            h, w = pov.shape[0], pov.shape[1]
            for rad in (6, 8, 12):
                patch = pov[h // 2 - rad:h // 2 + rad + 1, w // 2 - rad:w // 2 + rad + 1].reshape(-1, 3)
                r_, g_, b_ = patch.mean(0)
                v = patch.max(1)
                print(f"eye={eye} dist={dist} rad={rad}: mean rgb {r_:.0f},{g_:.0f},{b_:.0f} "
                      f"v p10/p50/p90 {np.percentile(v,10):.0f}/{np.percentile(v,50):.0f}/{np.percentile(v,90):.0f} "
                      f"green share {((patch[:,1] > patch[:,0] + 15) & (patch[:,1] > patch[:,2] + 5) & (patch[:,1] > 60)).mean():.2f}",
                      flush=True)
            print("   pos", rig.pos(), "aim", round(pitch, 1), round(yaw, 1), round(d, 2), flush=True)
    # a raised frame (side faces exposed), eye=false, from 1 block
    rig.cmd(f"/setblock {fx} {fy + 1} {fz} minecraft:end_portal_frame[eye=false,facing=south]")
    pos = {"x": fx + 0.5, "y": float(by), "z": fz - 0.5, "pitch": 0.0, "yaw": 0.0}
    pitch, yaw, d = MW.angles_to(pos, (fx + 0.5, fy + 1.81, fz + 0.5))
    rig.tp(fx + 0.5, by, fz - 0.5, yaw=yaw, pitch=pitch)
    rig.idle(8)
    rig.frame("frame_raised_false")
    pov = np.asarray(rig.info["pov"]).astype(np.float32)
    h, w = pov.shape[0], pov.shape[1]
    patch = pov[h // 2 - 8:h // 2 + 9, w // 2 - 8:w // 2 + 9].reshape(-1, 3)
    print("raised eye=false rad=8: mean rgb %.0f,%.0f,%.0f green share %.2f" % (*patch.mean(0), ((patch[:,1] > patch[:,0] + 15) & (patch[:,1] > patch[:,2] + 5) & (patch[:,1] > 60)).mean()), flush=True)
finally:
    rig.close()
print("PROBE DONE", out, flush=True)
