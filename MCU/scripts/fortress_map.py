#!/usr/bin/env python3
"""Instrument (no model): map the Nether fortress the default world's `/locate` names, from
the engine's voxel channel -- where its brick walkways are, where a blaze spawner stands,
and which cells an avatar can be put on. Writes JSON; nothing here is shown to an agent."""
from __future__ import annotations

import argparse, json, math, os, sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")
ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("output/fortress_map.json"))
    ap.add_argument("--cx", type=int, default=-597)
    ap.add_argument("--cz", type=int, default=-245)
    ap.add_argument("--span", type=int, default=72)       # half-width scanned around the centre
    args = ap.parse_args()

    from util import load_world_spec
    from mcu_worldmodel import portal
    from mcu_worldmodel.craft_env import patch_minecraft_sim
    from mcu_worldmodel.milestones import location
    from mcu_worldmodel.procedures import noop

    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim
    from minestudio.simulator.callbacks import CommandsCallback

    cmds = ["/effect give @s minecraft:resistance 100000 4 true",
            "/effect give @s minecraft:fire_resistance 100000 0 true",
            f"/execute in minecraft:the_nether run forceload add {args.cx - 96} {args.cz - 96} {args.cx + 96} {args.cz + 96}"]
    sim = MinecraftSim(action_type="env", obs_size=(128, 128), render_size=(640, 360),
                       callbacks=[CommandsCallback(cmds)], **load_world_spec("ender_dragon"))
    obs, info = sim.reset()
    for _ in range(20):
        obs, _, _, _, info = sim.step(noop())
    keep: dict[tuple[int, int, int], str] = {}
    solid: set[tuple[int, int, int]] = set()
    boxes = []
    W = 24
    for y in (56, 76):
        for dx in range(-args.span, args.span + 1, 2 * W):
            for dz in range(-args.span, args.span + 1, 2 * W):
                x, z = args.cx + dx, args.cz + dz
                sim.env.execute_cmd(f"/execute in minecraft:the_nether run tp @s {x}.5 {y} {z}.5")
                for _ in range(6):
                    obs, _, _, _, info = sim.step(noop())
                act = noop(); act["voxels"] = [-W, W, -10, 10, -W, W]
                obs, _, _, _, info = sim.step(act)
                pos = location(info)
                o = (math.floor(pos["x"]), math.floor(pos["y"]), math.floor(pos["z"]))
                blocks = portal.parse_voxels(info.get("voxels"), o)
                if blocks is None:
                    print("unreadable voxels at", o, str(info.get("voxels"))[:200]); continue
                boxes.append([o[0] - W, o[0] + W, o[1] - 10, o[1] + 10, o[2] - W, o[2] + W])
                for c, t in blocks.items():
                    solid.add(c)
                    if any(k in t for k in ("nether_brick", "spawner", "chest", "nether_wart", "soul_sand")):
                        keep[c] = t.replace("minecraft:", "")
                print("scanned", o, len(blocks), flush=True)
    kinds = Counter(keep.values())
    spawners = sorted(c for c, t in keep.items() if t == "spawner")

    def inside(c):
        return any(b[0] <= c[0] < b[1] and b[2] <= c[1] < b[3] and b[4] <= c[2] < b[5] for b in boxes)

    # a standing cell: a nether-brick block with three scanned air cells above it
    stand = [c for c, t in keep.items() if t == "nether_bricks"
             and all(inside((c[0], c[1] + k, c[2])) and (c[0], c[1] + k, c[2]) not in solid for k in (1, 2, 3))]
    by_y = Counter(c[1] for c in stand)
    out = {"centre": [args.cx, args.cz], "kinds": dict(kinds), "spawners": spawners,
           "standing_cells_by_y": dict(sorted(by_y.items())), "standing": sorted(stand),
           "bricks_bbox": [[min(c[i] for c in keep), max(c[i] for c in keep)] for i in range(3)] if keep else None,
           "boxes": boxes}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out))
    print(json.dumps({k: out[k] for k in ("kinds", "spawners", "standing_cells_by_y", "bricks_bbox")}))
    sim.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
