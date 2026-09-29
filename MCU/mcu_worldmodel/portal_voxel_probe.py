r"""Live test: does the engine's voxel channel say what `portal.py` assumes it says?

The nether-portal case study is scored entirely from `info["voxels"]`, and every claim
in that sentence came from decompiling `EnvServer`, not from a run:

    the key comes back      sending `action["voxels"] = [x0, x1, y0, y1, z0, z1]` makes
                            the client answer at all
    offsets, not absolutes  each hit's x/y/z is relative to the PLAYER'S block position
    air is omitted          a cell is proved clear by being inside the box and absent
    the top bound is open   the loops are `range(x0, x1)`, so (0, 1) is one column
    the name is the full id `minecraft:obsidian`, from `ResourceLocation.getFullName()`

Get any of them wrong and nothing raises: `portal_report.json` is written, every frame
scores 0/10, and a wave of arms looks like it failed at geometry when it failed at
plumbing. The same mistake shape as `aba_bucket_probe`, and settled the same way --
minutes on a node, before the wave.

Also checks the two things only the engine can settle for this task: that
`CommandsCallback` actually delivers ten obsidian and a flint and steel, and that a
portal assembled by `/setblock` reads back through `portal.best_fit` as complete, and
as lit once fire is put inside it.

Writes JSON to stdout and to --out. Exit 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

TASK = "nether_portal"


def _origin(info: dict) -> tuple[int, int, int]:
    from mcu_worldmodel.milestones import location
    pos = location(info)
    return (math.floor(pos["x"]), math.floor(pos["y"]), math.floor(pos["z"]))


def _inventory(info: dict) -> dict:
    return {v.get("type"): int(v.get("quantity", 0))
            for v in (info.get("inventory") or {}).values()
            if isinstance(v, dict) and v.get("type") not in (None, "air", "none")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("output/portal_voxel_probe.json"))
    ap.add_argument("--task", default=TASK)
    args = ap.parse_args(argv)

    out: dict = {"task": args.task, "ok": False, "checks": {}, "error": None}

    from util import get_tasks, load_world_spec, load_portal_probe
    from mcu_worldmodel import portal
    from mcu_worldmodel.craft_env import patch_minecraft_sim
    from mcu_worldmodel.procedures import noop

    tasks = {t[0]: t for t in get_tasks(args.task)}
    _name, commands, _text, _reward, _milestones = tasks[args.task]
    spec = load_portal_probe(args.task)
    window = tuple(spec.get("window") or (-8, 9, -5, 6, -8, 9))
    out["config"] = {"window": list(window), "commands": len(commands)}

    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim
    from minestudio.simulator.callbacks import CommandsCallback

    sim = None
    checks = out["checks"]
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360),
                           callbacks=[CommandsCallback(commands)],
                           **load_world_spec(args.task))
        obs, info = sim.reset()
        for _ in range(20):          # let the /fill settle before anything is read
            obs, _, _, _, info = sim.step(noop())

        inv = _inventory(info)
        out["inventory"] = inv
        checks["kit_delivered"] = (inv.get("obsidian", 0) >= 10
                                   and inv.get("flint_and_steel", 0) >= 1)

        def ask(win):
            """One voxel query, returning the raw answer and the parsed absolute map."""
            nonlocal obs, info
            act = noop()
            act["voxels"] = list(win)
            obs, _, _, _, info = sim.step(act)
            raw = info.get("voxels")
            return raw, portal.parse_voxels(raw, _origin(info))

        raw, blocks = ask(window)
        out["raw_sample"] = str(raw)[:400]
        checks["channel_present"] = raw is not None
        checks["shape_readable"] = blocks is not None
        if not checks["shape_readable"]:
            out["error"] = ("info['voxels'] is not the list-of-{x,y,z,type} shape "
                            "portal.parse_voxels expects; see raw_sample")
            return 1

        ox, oy, oz = _origin(info)
        # The pad is stone at feet-1 and air above, so these two settle "relative, not
        # absolute" and "air omitted" in one answer.
        checks["offsets_are_relative"] = (ox, oy - 1, oz) in blocks
        checks["air_is_omitted"] = (ox, oy + 2, oz) not in blocks
        out["floor_block"] = blocks.get((ox, oy - 1, oz))

        # A marker at a known offset: the arithmetic, end to end.
        sim.env.execute_cmd("/setblock ~3 ~ ~ minecraft:gold_block")
        for _ in range(4):
            obs, _, _, _, info = sim.step(noop())
        ox, oy, oz = _origin(info)
        _raw, blocks = ask(window)
        checks["marker_at_the_right_cell"] = (
            blocks.get((ox + 3, oy, oz)) == "minecraft:gold_block")

        # The upper bound: a box that stops at the marker's column must not contain it.
        _raw, narrow = ask((0, 3, 0, 1, 0, 1))
        checks["upper_bound_is_exclusive"] = (ox + 3, oy, oz) not in narrow

        # A portal built by hand, read back through the scorer. Four blocks east of the
        # player so nothing of the avatar is inside it.
        sim.env.execute_cmd("/setblock ~3 ~ ~ minecraft:air")
        base = (ox + 4, oy, oz - 1)          # interior bottom-left, plane along z
        cells = portal.frame_cells(base, "z")
        for cell in cells.required:
            sim.env.execute_cmd(f"/setblock {cell[0]} {cell[1]} {cell[2]} minecraft:obsidian")
        for cell in cells.interior:
            sim.env.execute_cmd(f"/setblock {cell[0]} {cell[1]} {cell[2]} minecraft:air")
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())
        _raw, blocks = ask(window)
        world = portal.World()
        world.apply(_origin(info), window, blocks)
        best = portal.best_fit(world)
        out["frame"] = best.as_dict() if best else None
        checks["setblock_frame_scores_complete"] = bool(best and best.complete)

        # Fire inside a legal frame is a portal; that is the only ground truth for "lit".
        fire = cells.interior[0]
        sim.env.execute_cmd(f"/setblock {fire[0]} {fire[1]} {fire[2]} minecraft:fire")
        for _ in range(20):
            obs, _, _, _, info = sim.step(noop())
        _raw, blocks = ask(window)
        world = portal.World()
        world.apply(_origin(info), window, blocks)
        best = portal.best_fit(world)
        out["frame_lit"] = best.as_dict() if best else None
        checks["fire_makes_a_portal"] = bool(best and best.lit)

        out["ok"] = all(checks.values())
    except Exception as exc:  # noqa: BLE001 - the report is the deliverable
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:  # noqa: BLE001
                pass
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))

    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
