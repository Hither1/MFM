"""Stage 18: re-open a placed table by replaying the pose that opened it.

obf1 (2026-09-06) lost ~10k steps and obf2 four re-opens by step 1073 to a remembered
cell one block off: `use_until_gui(item=)` aimed at the 55-degree-ray estimate of the
placed cell and pressed at air. The pose the screen actually opened from is exact.
Here: (1) flat ground -- place and open, close, walk 6 blocks away, re-open: the
replay walks back and the screen comes up; (2) the obf2 case -- the floor one block
ahead is a hole, so the table lands a block LOWER than the estimate; the replay still
opens it, and (informatively) the estimated cell disagrees with the recorded pose.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import SPAWN, P, Rig, main_guard

Y = 30


def _hall(rig: Rig, bx: int, bz: int) -> None:
    rig.fill(bx - 10, Y - 6, bz - 10, bx + 10, Y + 6, bz + 12, "stone")
    rig.fill(bx - 8, Y, bz - 8, bx + 8, Y + 1, bz + 10, "air")
    for zz in range(bz - 7, bz + 10, 3):
        rig.fill(bx - 7, Y + 2, zz, bx + 7, Y + 2, zz, "glowstone")


def _reopen_round(rig: Rig, label: str, bx: int, bz: int, hole: bool) -> None:
    grid = rig.agent.grid
    grid.opened.pop("crafting_table", None)
    grid.placed.pop("crafting_table", None)
    rig.agent._placed.pop("crafting_table", None)
    rig.ensure_closed()
    rig.tp(bx + 0.5, Y, bz + 2.5, yaw=0, pitch=0)         # facing +z
    if hole:
        rig.fill(bx, Y - 1, bz + 3, bx, Y - 1, bz + 3, "air")   # the cell ahead is a step down
    rig.idle(10)
    r = rig.run([P("place_and_open", item="crafting_table")], label=f"{label}: place_and_open",
                max_ticks=200)
    rig.frame(f"s18_{label}_placed")
    rig.check(f"{label}: the table screen opened after placing",
              r["gui"] and r["screen"] == "table", (r["gui"], r["screen"], r["notes"][-2:]))
    op = grid.opened.get("crafting_table")
    rig.check(f"{label}: the opening pose is on record", op is not None and op.get("pose"), op)
    est = (grid.placed.get("crafting_table") or {}).get("cell")
    rig.log(f"{label}: estimated cell {est}, opening pose {op and op['pose']}")
    rig.run([P("close_inventory")], label=f"{label}: close", max_ticks=60)
    r = rig.run([P("go_to", x=bx + 0.5, z=bz - 3.5, within=0.6, n=160)],
                label=f"{label}: walk away", max_ticks=240)
    p = rig.pos()
    rig.check(f"{label}: walked 5+ blocks away", p is not None and p["z"] <= bz - 2.5, p)
    rig.check(f"{label}: no screen open before the re-open", not rig.info.get("isGuiOpen"))
    r = rig.run([P("use_until_gui", n=8, item="crafting_table")],
                label=f"{label}: use_until_gui(item=crafting_table)", max_ticks=320)
    rig.frame(f"s18_{label}_reopened")
    rig.check(f"{label}: the screen opened again by the replayed pose",
              r["gui"] and r["screen"] == "table" and r["stats"].get("pose_reopens", 0) == 1,
              (r["gui"], r["screen"], r["stats"], r["notes"][-2:]))
    rig.check(f"{label}: no 'no screen opened' note",
              not any("no screen opened" in n for n in r["notes"]), r["notes"][-2:])
    if hole:
        rig.check("hole: the estimate and the pose disagree by a block (the obf2 case)",
                  est is not None and op is not None
                  and abs(float(op["pose"]["y"]) - est[1]) < 1.5, (est, op))
    rig.run([P("close_inventory")], label=f"{label}: close again", max_ticks=60)


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    _hall(rig, bx, bz)
    rig.tp(bx + 0.5, Y, bz + 2.5, yaw=0, pitch=0)
    rig.clear()
    rig.give("crafting_table", 2)
    rig.give("cobblestone", 8)
    rig.idle(20)
    _reopen_round(rig, "flat", bx, bz, hole=False)
    # the second round on fresh ground 6 blocks east, with the hole ahead
    bx2 = bx + 6
    rig.fill(bx2 - 3, Y, bz - 8, bx2 + 3, Y + 1, bz + 10, "air")
    _reopen_round(rig, "hole", bx2, bz, hole=True)


if __name__ == "__main__":
    main_guard(stage)
