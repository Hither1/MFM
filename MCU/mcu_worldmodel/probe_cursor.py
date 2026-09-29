"""Does a camera delta move the GUI cursor at all?

This asks the question directly, with no dependence on slot coordinates, scale factors or
accumulated bookkeeping -- all three of which confounded the earlier attempts. Open the
inventory, capture the frame, move the camera, capture again, and compare pixels. If the
cursor moved, the images differ; the cursor is the only thing that can change on a static
inventory screen.

It also checks the GUI toggle itself, because the previous calibration ended with the
inventory unexpectedly closed, which means its close/open cycling had slipped phase and an
unknown share of its 1089 candidates were clicking at the world instead of at slots.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

import numpy as np
from loguru import logger

from mcu_worldmodel.craft_env import patch_minecraft_sim
from mcu_worldmodel.procedures import act, noop


def main() -> int:
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim

    out: dict = {"error": None, "steps": []}
    sim = None
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360), callbacks=[])
        obs, info = sim.reset()
        sim.env.execute_cmd("/give @p minecraft:oak_planks 16")
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())

        def pov():
            return np.asarray(info["pov"]).astype(np.int16)

        def record(label, frame_a, frame_b):
            diff = int(np.abs(frame_a - frame_b).sum())
            changed = int((np.abs(frame_a - frame_b).sum(axis=2) > 12).sum())
            out["steps"].append({"stage": label, "abs_diff": diff,
                                 "pixels_changed": changed,
                                 "gui_open": bool(info.get("isGuiOpen"))})
            logger.info(f"[cursor] {label}: pixels_changed={changed} "
                        f"gui_open={info.get('isGuiOpen')}")

        # 1. how many ticks does the inventory toggle actually need?
        before = pov()
        for a in [act(inventory=1)]:
            obs, _, _, _, info = sim.step(a)
        record("after 1 tick of inventory press", before, pov())
        for _ in range(4):
            obs, _, _, _, info = sim.step(noop())
        record("after 4 settle ticks", before, pov())
        out["gui_open_after_toggle"] = bool(info.get("isGuiOpen"))
        if not out["gui_open_after_toggle"]:
            out["error"] = "inventory did not open; every later result is meaningless"
            return 1

        # 2. does a camera delta change the screen while the GUI is up?
        for mag in (1.8, 5.0, 18.0, 45.0):
            base = pov()
            steps = max(1, int(mag // 8) + 1)
            for _ in range(steps):
                obs, _, _, _, info = sim.step(act(camera=[0.0, mag / steps]))
            for _ in range(2):
                obs, _, _, _, info = sim.step(noop())
            record(f"camera yaw +{mag} deg with GUI open", base, pov())

        # 3. does the same delta change the screen with the GUI CLOSED?
        #    (a control: if it changes there and not here, camera drives the head, not the
        #    cursor, and GUI cursor control is something else entirely)
        for a in [act(inventory=1), noop(), noop(), noop()]:
            obs, _, _, _, info = sim.step(a)
        out["gui_open_after_close"] = bool(info.get("isGuiOpen"))
        base = pov()
        for _ in range(3):
            obs, _, _, _, info = sim.step(act(camera=[0.0, 6.0]))
        for _ in range(2):
            obs, _, _, _, info = sim.step(noop())
        record("camera yaw +18 deg with GUI CLOSED (control)", base, pov())
    except Exception as e:
        logger.exception("[cursor] failed")
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass

    print("\n=== CURSOR MOTION PROBE ===")
    print(json.dumps(out, indent=2, default=str))
    gui_moves = [s for s in out["steps"] if "GUI open" in s["stage"]]
    if gui_moves:
        moved = [s for s in gui_moves if s["pixels_changed"] > 20]
        print("\nCamera moves something on the inventory screen:",
              bool(moved), f"({len(moved)}/{len(gui_moves)} magnitudes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
