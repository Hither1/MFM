"""Stage 23: the shaft guard stops a walk before the avatar's own open shaft.

og9_mfm (2026-09-07, step 19286): a mine_forward from a stair at y 67 broke into the
y 9..67 shaft it had dug at steps 3955-4663 one block away; the avatar walked into the
column, fell 58 blocks and died with the kit. The column was on its map as walked cells.
Here a 1x2 hole nine blocks deep is cut through a lit platform. Control: with the map
blank the go_to across it falls in. Then the map is taught the columns as a dig_down
records them (every level, top first) and a go_to across it (the servo sprint-jumps)
must stop on the platform with one SHAFT AHEAD note; raw `forward` held from 0.8 block
off the edge must stop too, and so must sneak + forward (the first run of this stage:
sneaking did NOT hold the avatar at the edge in this simulator).
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 80, -5500
DEPTH = 9


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    rig.platform(X, Y, Z, r=8, block="stone")
    for xx in range(X - 6, X + 7, 4):
        rig.fill(xx, Y + 4, Z - 7, xx, Y + 4, Z + 7, "glowstone")
    # the hole: solid walls around a 1x2 column, open from the platform down DEPTH blocks
    rig.fill(X - 1, Y - DEPTH, Z + 2, X + 1, Y - 1, Z + 5, "stone")
    rig.fill(X, Y - DEPTH + 1, Z + 3, X, Y, Z + 4, "air")
    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=0)         # facing +z, the hole ahead
    rig.clear()
    rig.idle(12)
    y0 = rig.pos()["y"]
    top = int(y0)

    r0 = rig.run([{"action": {"forward": 1}, "repeat": 40}],
                 label="control: forward across the hole, map blank", max_ticks=80)
    p = rig.pos()
    rig.check("control: with the columns not on the map the walk falls into the hole",
              p["y"] <= y0 - 3, (y0, p, r0["stats"]))

    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=0)
    rig.idle(12)
    # teach the map the two columns as a dig_down records them: every level, top first
    g = rig.agent.grid
    step = int(getattr(rig.agent, "step", 0)) + 1000
    for z in (Z + 3, Z + 4):
        for y in range(top, Y - DEPTH, -1):
            g.observe(step, {"x": X + 0.5, "y": float(y), "z": z + 0.5, "pitch": 0.0, "yaw": 0.0})
            step += 5
    d = g.drop_ahead((X, top, Z + 3))
    rig.check("the map reads the column as a shaft (drop_ahead)", d is not None and d["drop"] == DEPTH, d)

    r1 = rig.run([P("go_to", x=X + 0.5, z=Z + 6.5, within=0.8)],
                 label="guarded: the same go_to", max_ticks=200)
    p = rig.pos()
    rig.check("the guard stopped the walk on the platform before the hole",
              p["y"] >= y0 - 0.5 and p["z"] < Z + 3, (y0, p))
    notes = [n for n in r1["notes"] if "SHAFT AHEAD" in n]
    rig.check("one SHAFT AHEAD note names the column, the levels and the drop",
              len(notes) == 1 and f"({X}, {top}, {Z + 3})" in notes[0]
              and f"falls {DEPTH} blocks" in notes[0] and f"down to y {Y - DEPTH + 1}" in notes[0],
              notes[:1])
    rig.check("the plan was dropped (shaft_stops 1, queue drained)",
              r1["stats"].get("shaft_stops") == 1 and r1["drained"], r1["stats"])

    # raw forward held from 0.8 block off the edge (og9's mine_forward geometry)
    rig.tp(X + 0.5, Y + 1, Z + 2.2, yaw=0, pitch=0)
    rig.idle(12)
    r2 = rig.run([{"action": {"forward": 1}, "repeat": 20}],
                 label="raw forward from 0.8 block off the edge", max_ticks=60)
    p = rig.pos()
    rig.check("raw forward at the edge: stopped, not fallen",
              p["y"] >= y0 - 0.5 and r2["stats"].get("shaft_stops") == 1, (p, r2["stats"]))

    # sneak + forward is stopped too (the first s23 run: sneaking walked off the edge)
    rig.tp(X + 0.5, Y + 1, Z + 2.2, yaw=0, pitch=0)
    rig.idle(12)
    r3 = rig.run([{"action": {"forward": 1, "sneak": 1}, "repeat": 20}],
                 label="sneak + forward at the edge", max_ticks=60)
    p = rig.pos()
    rig.check("sneak + forward at the edge: stopped, not fallen",
              r3["stats"].get("shaft_stops") == 1 and p["y"] >= y0 - 0.5, (p, r3["stats"]))
    rig.frame("s23_after")


if __name__ == "__main__":
    main_guard(stage)
