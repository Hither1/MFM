"""Locate the GUI cursor by watching which pixels it changes.

Every previous attempt inferred the cursor's position from assumptions -- that it opens at
the screen centre, that an over-large move clamps it to a corner, that a bookkeeping
counter tracked it. All three were wrong, and each produced a well-formed craft that moved
nothing.

`probe_cursor.py` established the facts this builds on: the inventory opens in ONE tick;
a camera delta with the GUI up changes ~2.4-3.1k pixels (the cursor sprite plus the slot
highlight under it) while the same delta with the GUI down changes ~141k (the whole world);
and a 45-degree delta changes only ~450px because the cursor clamps at the screen edge.

So the cursor is directly observable: move it, diff the frames, and the centroid of the
changed pixels is where it went. This measures, in one episode and with no toggling after
the initial open:

  * the cursor position when the inventory opens,
  * the true pixels-per-degree,
  * whether an over-large move really does clamp to a corner.

The toggle is pressed exactly once. The earlier 1089-candidate scan toggled twice per
candidate, and because the toggle is edge-triggered on a single tick, one missed edge
inverts the phase for every candidate after it -- which is why that scan reported a null
result and why its output ended with the inventory unexpectedly closed.
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

THRESH = 12          # per-pixel channel delta that counts as "changed"


def main() -> int:
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim

    out: dict = {"error": None, "samples": []}
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

        def centroid(a, b):
            """(x, y) of the changed region, or None if nothing changed."""
            mask = (np.abs(a - b).sum(axis=2) > THRESH)
            n = int(mask.sum())
            if n < 8:
                return None, n
            ys, xs = np.nonzero(mask)
            return (float(xs.mean()), float(ys.mean())), n

        def move(deg_x, deg_y=0.0):
            nonlocal obs, info
            steps = max(1, int(max(abs(deg_x), abs(deg_y)) // 6) + 1)
            for _ in range(steps):
                obs, _, _, _, info = sim.step(act(camera=[deg_y / steps, deg_x / steps]))
            for _ in range(2):
                obs, _, _, _, info = sim.step(noop())

        # Open ONCE. Never toggle again.
        obs, _, _, _, info = sim.step(act(inventory=1))
        for _ in range(4):
            obs, _, _, _, info = sim.step(noop())
        out["gui_open"] = bool(info.get("isGuiOpen"))
        if not out["gui_open"]:
            out["error"] = "inventory did not open"
            return 1

        # A small nudge and back: the union of the two changed regions brackets the
        # cursor's resting place, which is what we want the opening position of.
        base = pov()
        move(3.0, 0.0)
        c1, n1 = centroid(base, pov())
        out["samples"].append({"stage": "nudge +3deg x", "centroid": c1, "pixels": n1})
        move(-3.0, 0.0)

        # Sweep right in fixed steps, recording where the change lands each time. The
        # spacing between consecutive centroids gives pixels-per-degree directly.
        track = []
        prev = pov()
        for i in range(1, 9):
            move(6.0, 0.0)
            c, n = centroid(prev, pov())
            track.append({"step": i, "deg_cumulative": 6.0 * i, "centroid": c, "pixels": n})
            prev = pov()
        out["sweep_x"] = track

        xs = [t["centroid"][0] for t in track if t["centroid"]]
        if len(xs) >= 3:
            deltas = [b - a for a, b in zip(xs, xs[1:]) if abs(b - a) > 1]
            if deltas:
                out["px_per_degree_measured"] = round(float(np.median(deltas)) / 6.0, 3)

        # Does an over-large move clamp? Slam left and see where the change ends up.
        prev = pov()
        move(-200.0, -200.0)
        c, n = centroid(prev, pov())
        out["clamp_topleft"] = {"centroid": c, "pixels": n}
        # ... then nudge right and read the cursor's post-clamp position.
        prev = pov()
        move(6.0, 0.0)
        c, n = centroid(prev, pov())
        out["after_clamp_nudge"] = {"centroid": c, "pixels": n}
    except Exception as e:
        logger.exception("[locate] failed")
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass

    print("\n=== CURSOR LOCATION ===")
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
