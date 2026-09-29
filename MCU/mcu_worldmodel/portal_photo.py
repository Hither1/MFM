r"""Photograph the frames the arms built, in the game, from a vantage they never took.

The point of this task is that the geometry is only checkable by looking -- and then no
run produced a picture of it. Every saved point-of-view frame is a close-up, because an
agent building a wall stands against the wall; scanning all 6,001 frames of each episode
with the repo's own `portal_fraction` and an obsidian colour band turned up nothing with
the whole 4x5 outline inside the view.

So this rebuilds them. `world_seed: 42` and a pinned spawn biome mean every run began at
the same block, so the cells in `portal_report.json` are absolute coordinates that still
address the same place in a fresh world. For each report: clear the volume, `/setblock`
exactly what that arm left standing, light it with fire if the frame is legal (so the
purple is the game's, not a texture we asserted), then put the camera eight blocks back
on the frame's axis in spectator mode -- no hand, no hotbar -- and read `obs["image"]`.

This is a reconstruction, and says so on the tin: it is what the arm built, not a frame
the arm saw. `figures/portal_frames_built.png` remains the measurement; this is the
photograph of it.

    python -m mcu_worldmodel.portal_photo --out figures/portal_ingame \
        arc=<...>/portal_report.json mfm=<...> logbook=<...> vista=<...>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")
ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

TASK = "nether_portal"


def blocks_at_end(report: dict) -> dict[tuple[int, int, int], str]:
    """What the arm left standing, replayed and stopped at the dimension change.

    Past the transit the voxel answers describe the Nether, whose portal the engine
    built -- see PortalTrace.observe.
    """
    cut = report.get("dimension_change_step") or 10 ** 9
    ev = [(p["step"], 1, tuple(p["cell"]), p["block"]) for p in report["placements"]]
    ev += [(r["step"], 0, tuple(r["cell"]), r["block"]) for r in report["removals"]]
    out: dict[tuple[int, int, int], str] = {}
    for step, add, cell, block in sorted(ev, key=lambda e: (e[0], e[1])):
        if step > cut:
            break
        if add:
            out[cell] = block
        else:
            out.pop(cell, None)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="+", help="label=path/to/portal_report.json")
    ap.add_argument("--out", type=Path, default=Path("figures/portal_ingame"))
    ap.add_argument("--back", type=int, default=9, help="blocks behind the frame plane")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    from util import get_tasks, load_world_spec
    from mcu_worldmodel import portal as P
    from mcu_worldmodel.craft_env import patch_minecraft_sim
    from mcu_worldmodel.procedures import noop
    import cv2
    import numpy as np

    tasks = {t[0]: t for t in get_tasks(TASK)}
    _n, commands, _t, _r, _m = tasks[TASK]
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim
    from minestudio.simulator.callbacks import CommandsCallback

    # obs_size is what `obs["image"]` is resized to; the untouched render stays in
    # `info["pov"]` (MinecraftSim._wrap_obs_info copies obs into info BEFORE resizing).
    # Photographing obs["image"] at the default 128x128 produced thumbnails.
    sim = MinecraftSim(action_type="env", obs_size=(640, 360), render_size=(640, 360),
                       callbacks=[CommandsCallback(commands)], **load_world_spec(TASK))
    obs, info = sim.reset()

    def run(cmd):
        sim.env.execute_cmd(cmd)

    def settle(n=12):
        nonlocal obs, info
        for _ in range(n):
            obs, _, _, _, info = sim.step(noop())

    settle(20)
    # Chat and toasts sit on top of the shot. `sendCommandFeedback false` kills the
    # "Changed the block at ..." line every /setblock prints, and `announceAdvancements
    # false` stops the "Advancement Made!" cards the kit's /give triggers. Neither
    # silences what has already been said, and Minecraft holds a chat line for ten
    # seconds -- hence the long wait before each shutter below. (Same two rules, same
    # reason, as the recall-probe builds.)
    run("/gamerule sendCommandFeedback false")
    run("/gamerule announceAdvancements false")
    run("/gamerule doDaylightCycle false")
    run("/time set noon")
    run("/gamemode spectator")
    written = []
    try:
        for spec in args.reports:
            label, _, path = spec.partition("=")
            rep = json.loads(Path(path).read_text(encoding="utf-8"))
            cells = blocks_at_end(rep)
            best = P.best_fit_from(cells) if hasattr(P, "best_fit_from") else None
            if best is None:
                w = P.World()
                for c, b in cells.items():
                    w.solid[c] = b
                    w.seen.add(c)
                fc0 = P.frame_cells(tuple(rep["best_frame"]["anchor"]),
                                    rep["best_frame"]["axis"])
                for c in set(fc0.required) | set(fc0.corners) | set(fc0.interior):
                    w.seen.add(c)
                best = P.best_fit(w)
            fc = P.frame_cells(best.anchor, best.axis)
            ax, ay, az = best.anchor

            # a clean volume, floor restored, then exactly what the arm left
            run(f"/fill {ax-11} {ay-2} {az-11} {ax+11} {ay+10} {az+11} minecraft:air")
            run(f"/fill {ax-11} {ay-2} {az-11} {ax+11} {ay-2} {az+11} minecraft:stone")
            settle(6)
            for cell, block in sorted(cells.items()):
                if block == "minecraft:fire":
                    continue                      # placed last, so it can form a portal
                if block == "minecraft:nether_portal":
                    continue                      # the fire makes these, faithfully
                run(f"/setblock {cell[0]} {cell[1]} {cell[2]} {block}")
            settle(8)
            if best.complete:                     # light it the way the game does
                inside = fc.interior[0]
                run(f"/setblock {inside[0]} {inside[1]} {inside[2]} minecraft:fire")
                settle(20)

            # camera: back along the axis perpendicular to the frame plane, centred
            u = (1, 0, 0) if best.axis == "x" else (0, 0, 1)
            cx = ax + u[0] * 0.5 + (0 if u[0] else 0.5)
            cz = az + u[2] * 0.5 + (0 if u[2] else 0.5)
            cy = ay + 1
            # Centre on the rectangle itself, not on the anchor: the frame spans one
            # column left of the interior and two right of it.
            span = [sum(c[i] * u[i] for i in range(3)) for c in fc.required + fc.corners]
            mid = (min(span) + max(span) + 1) / 2.0
            if best.axis == "x":                  # plane varies in x, fixed z -> stand off in z
                px, pz, yaw = mid, az - args.back, 0.0             # yaw 0 faces +z
            else:                                 # varies in z, fixed x -> stand off in x
                px, pz, yaw = ax - args.back, mid, -90.0           # yaw -90 faces +x
            run(f"/tp @s {px:.1f} {cy:.1f} {pz:.1f} {yaw:.1f} 0")
            # Ten seconds of ticks, so every chat line from the build has expired.
            settle(230)
            img = np.asarray(info.get("pov") if info.get("pov") is not None
                             else obs["image"])
            out = args.out / f"{label}_ingame.png"
            cv2.imwrite(str(out), img[:, :, ::-1])
            written.append((label, str(out), f"{best.n_matched}/10", best.lit))
            print(f"[photo] {label}: {best.n_matched}/10 lit={best.lit} -> {out}", flush=True)
    finally:
        try:
            sim.close()
        except Exception:  # noqa: BLE001
            pass
    print(json.dumps(written, indent=2))
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
