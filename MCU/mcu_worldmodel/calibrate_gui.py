"""Measure the GUI cursor mapping instead of deriving it.

`gui.py`'s geometry is arithmetic from Minecraft's fixed container layout, but the one
number it cannot derive is how a camera delta moves the cursor *inside* a GUI. The derived
value (10 px per degree, from `MOUSE_MULTIPLIER = 0.1`) produced a well-formed craft that
moved nothing, twice -- so it is wrong, or the corner-clamp assumption behind the origin is.

This sweeps both in one episode. The test is unambiguous and needs no vision: put a known
stack in a known slot, open the inventory, aim at that slot, left-click. If the aim was
right the stack is picked up onto the cursor and the slot reads empty in
`info['inventory']`. Clicking again puts it back, so each candidate starts from the same
state.

Prints the candidates that worked, for pasting into gui.py.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

from loguru import logger

from mcu_worldmodel import gui
from mcu_worldmodel.craft_env import patch_minecraft_sim
from mcu_worldmodel.procedures import act, noop

#: Degrees of camera per 18px slot, from MOUSE_MULTIPLIER=0.1 at guiscale 1. The agent's
#: own successful crafts used exactly this unit (`cursor_to(dx=-2)` etc.), so it is not in
#: question -- what is in question is where the cursor STARTS.
DEG_PER_SLOT = 1.8
TEST_SLOT = 0                       # hotbar slot 0; /give fills it first

# The scan range, in slots, around the cursor's unknown start position. The inventory is
# 9 slots wide and the whole container about 9 tall, so +-7 covers it from anywhere inside.
SCAN = range(-7, 8)


def _hops(dx_deg: float, dy_deg: float, limit: float = 8.0):
    from mcu_worldmodel.procedures import act
    steps = max(1, int(max(abs(dx_deg), abs(dy_deg)) // limit) + 1)
    return [act(camera=[dy_deg / steps, dx_deg / steps]) for _ in range(steps)]


def main() -> int:
    """Probe one offset per GUI open, so no candidate inherits a clamped cursor.

    The previous version walked a serpentine path clicking at every stop, and reported the
    offset at which slot 0 was picked up. That number was wrong: Minecraft clamps the mouse
    to the window, so once the path ran into an edge the bookkeeping position and the real
    cursor diverged, and the "measured" offset was only where the counter stood when the
    real cursor happened to cross the slot. Encoding it produced another craft that moved
    nothing.

    Closing and reopening the inventory returns the cursor to its opening position, so each
    candidate here starts from the same known state and a hit means what it says.
    """
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim
    from mcu_worldmodel.procedures import act, noop

    out: dict = {"hit": None, "error": None, "tried": 0, "candidates": []}
    sim = None
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360), callbacks=[])
        obs, info = sim.reset()
        sim.env.execute_cmd("/give @p minecraft:oak_planks 16")
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())

        def slot_type(i):
            e = (info.get("inventory") or {}).get(i) or {}
            return e.get("type", "?")

        def step_all(actions):
            nonlocal obs, info
            for a in actions:
                obs, _, _, _, info = sim.step(a)

        if slot_type(TEST_SLOT) != "oak_planks":
            out["error"] = f"expected planks in slot {TEST_SLOT}, got {slot_type(TEST_SLOT)}"
            return 1

        # Coarse then fine: a half-slot grid over the plausible range. Slot boxes are 16px
        # inside an 18px pitch, so a half-slot step cannot step over a slot.
        cands = [(x / 2.0, y / 2.0) for y in range(-16, 17) for x in range(-16, 17)]
        for gx, gy in cands:
            step_all([act(inventory=1), noop(), noop()])       # close
            step_all([act(inventory=1), noop(), noop()])       # reopen -> cursor reset
            step_all(_hops(gx * DEG_PER_SLOT, gy * DEG_PER_SLOT))
            step_all([act(attack=1), act(attack=1), noop()])
            out["tried"] += 1
            if slot_type(TEST_SLOT) != "oak_planks":
                out["hit"] = {"dx_slots": gx, "dy_slots": gy}
                logger.success(f"[calibrate] slot {TEST_SLOT} picked up at "
                               f"({gx}, {gy}) slots from the GUI-open cursor")
                # put it back so the state is clean if we keep going
                step_all([act(attack=1), act(attack=1), noop()])
                break
        out["gui_open_after"] = bool(info.get("isGuiOpen"))
    except Exception as e:
        logger.exception("[calibrate] failed")
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass

    print("\n=== GUI CURSOR ORIGIN (reset between candidates) ===")
    print(json.dumps(out, indent=2, default=str))
    if out["hit"]:
        gx, gy = out["hit"]["dx_slots"], out["hit"]["dy_slots"]
        cx, cy = gui.centre(gui.slot_topleft(TEST_SLOT))
        open_x = cx - gx * gui.SLOT_PITCH
        open_y = cy - gy * gui.SLOT_PITCH
        print(f"\nCURSOR_OPEN (container coords) = ({open_x:.1f}, {open_y:.1f})")
        print(f"  slot {TEST_SLOT} centre {(cx, cy)}, offset ({gx}, {gy}) slots")
    else:
        print("\nNo offset picked the stack up. Camera may not move the GUI cursor at "
              "all in this engine, or `attack` is not a click on this screen.")
    return 0 if out["hit"] else 1


if __name__ == "__main__":
    sys.exit(main())
