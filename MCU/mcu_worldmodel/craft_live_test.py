"""Live test: does the GUI geometry in gui.py actually craft in the real engine?

The geometry is derived from Minecraft's fixed container layout and MOUSE_MULTIPLIER, so
it is arithmetic rather than a guess -- but the conversion from a camera delta to cursor
motion inside a GUI is a direction of travel that only the engine can confirm. This runs
it: hand the player planks, open the inventory, craft a table, and check the game's own
`craft_item` statistic.
"""
import json
import os
import sys

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

from loguru import logger

from mcu_worldmodel import gui
from mcu_worldmodel.craft_env import patch_minecraft_sim
from mcu_worldmodel.procedures import act, expand, noop


def main() -> int:
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim

    out = {"crafted": False, "error": None}
    sim = None
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360), callbacks=[])
        obs, info = sim.reset()
        sim.env.execute_cmd("/give @p minecraft:oak_planks 16")
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())

        inv = {k: v["type"] for k, v in (info.get("inventory") or {}).items()
               if isinstance(v, dict) and v.get("type") != "air"}
        out["inventory_before"] = inv
        ok, why = gui.can_craft(info, "crafting_table")
        out["can_craft"] = [ok, why]
        if not ok:
            out["error"] = f"planks did not arrive: {why}"
            return 1

        before = float((info.get("craft_item") or {}).get("crafting_table", 0) or 0)

        # open the inventory, craft, close
        seq, note = expand("open_inventory")
        for a in seq:
            obs, _, _, _, info = sim.step(a)
        out["gui_open"] = bool(info.get("isGuiOpen"))

        actions, why = gui.craft_actions(info, "crafting_table")
        out["craft_ticks"] = len(actions)
        for a in actions:
            obs, _, _, _, info = sim.step(a)
        for _ in range(6):
            obs, _, _, _, info = sim.step(noop())

        after = float((info.get("craft_item") or {}).get("crafting_table", 0) or 0)
        out.update(craft_before=before, craft_after=after, crafted=after > before)
        out["inventory_after"] = {
            k: f"{v['type']}x{int(v['quantity'])}"
            for k, v in (info.get("inventory") or {}).items()
            if isinstance(v, dict) and v.get("type") != "air"}
    except Exception as e:
        logger.exception("[craft_live_test] failed")
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass

    print("\n=== LIVE CRAFT TEST ===")
    print(json.dumps(out, indent=2, default=str))
    print("\nVERDICT:", "GUI CRAFT WORKS" if out.get("crafted") else "did not craft")
    return 0 if out.get("crafted") else 1


if __name__ == "__main__":
    sys.exit(main())
