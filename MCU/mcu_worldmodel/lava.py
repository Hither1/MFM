"""Where the lava in the view is: cells on the ground from the frame and the pose.

What is left of the harness's Nether macros (2026-10-24: no arm has a built-in procedure,
procedures.py): the lava band of `vision` cast onto the ground from the exact [STATE] pose,
remembered across turns, and the one sentence the runner's lava note gives the model.
The runner's lava guard (`harness_reflexes`, off in every arm) is its only reader.
"""
from __future__ import annotations

import math
from typing import Any


from mcu_worldmodel import geometry as MW


#: The camera's field of view: 70 degrees down the height (Minecraft's FOV setting is
#: the VERTICAL one) and ~102 across at 16:9, which is the same camera read the other way
#: -- tan(h/2) = (16/9) * tan(35) = 1.245, h = 102.3 (the tree world's measurement,
#: confirmed on the engine in a staged scene).
LAVA_HFOV, LAVA_VFOV = 102.0, 70.0


#: Below this depression the near edge of the mass is at or above the horizon: it is a
#: lava FALL down a wall, or the far shore of something huge, and no ground distance
#: follows from one row. Above 88 the tangent explodes.
LAVA_DEP_MIN, LAVA_DEP_MAX = 2.0, 88.0


#: Beyond this the estimate is a guess at a pixel row's precision (one row of 360 at 20
#: blocks moves it ~2 blocks), so the note says "about" and the walk closes in first.
LAVA_DIST_MAX = 32.0


def lava_ray(pitch: float, yaw: float, cx: float, row: float) -> tuple[float, float]:
    """(bearing, depression) in degrees of the world ray through the pixel at column
    `cx` (-0.5..0.5 of the width) and row `row` (0..1 of the height).

    The projection is rectilinear, not "so many degrees per pixel": a pixel's offset is
    linear in the TANGENT of its angle. Reading it linearly costs 6 degrees at a third of
    the width from the crosshair (30 degrees vs the true 36), which is 0.7 blocks of
    lateral error on a pool 7 blocks off, so the ray is built properly here: the camera
    basis (forward at `pitch`/`yaw`, right, up), the pixel's direction in it, and the
    bearing and depression read back off the world vector. Exact for any offset and any
    pitch, where `pitch + (row - 0.5) * 70` is only exact down the centre column.
    """
    th = math.tan(math.radians(LAVA_HFOV / 2.0))
    tv = math.tan(math.radians(LAVA_VFOV / 2.0))
    p, hx, hz = math.radians(pitch), *MW.facing(yaw)
    # forward (pitch down positive), right (the heading 90 degrees clockwise), up
    f = (hx * math.cos(p), -math.sin(p), hz * math.cos(p))
    rx, rz = MW.facing(yaw + 90.0)
    r = (rx, 0.0, rz)
    u = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
    a, b = 2.0 * th * float(cx), 2.0 * tv * (0.5 - float(row))
    d = (f[0] + a * r[0] + b * u[0], f[1] + a * r[1] + b * u[1],
         f[2] + a * r[2] + b * u[2])
    horiz = math.hypot(d[0], d[2])
    return (math.degrees(math.atan2(-d[0], d[2])),
            math.degrees(math.atan2(-d[1], horiz)) if horiz > 1e-9
            else (90.0 if d[1] < 0 else -90.0))


def lava_cells(pos: dict[str, float], cx: float, bottom: float,
               top: float | None = None, min_dist: float = 2.0,
               max_drop: int = 6) -> dict[str, Any] | None:
    """Where the lava of a `vision.lava_view` reading is, as game cells.

    One frame gives two angles -- the bearing of the mass's centre and the depression of
    its NEAR edge -- and the avatar's own eye height (1.62 above the feet) closes the
    triangle: a surface `EYE + drop` below the eye seen `dep` degrees down lies
    `(EYE + drop) / tan(dep)` blocks away.

    `drop` does not follow from one ray -- but it mostly does not have to. When the pool
    lies in a pit, its near edge is OCCLUDED by the pit's lip: the steepest ray that
    still reaches lava is the one grazing the lip, and that ray's depression is
    `atan(EYE / L)` for the lip's distance L whatever the pit's depth. So reading the
    lowest lava row with `drop = 0` returns the distance to the near edge of the HOLE in
    both cases -- which is where the rim block to pour from is. `drop` is escalated only
    when even that puts the lava nearer than `min_dist`, i.e. when the avatar stands at
    the edge looking down into a lake below the floor, and then it says how far under.
    The same lip has a second consequence, measured in a staged scene: a pool `drop` blocks
    down is INVISIBLE from further than `W * EYE / drop` (W = the pool's own width), so a
    3-wide pool one block under the floor cannot be seen at all beyond ~4.8 blocks. A
    sunk pool is therefore found near or not at all -- which is why find_lava walks its
    legs at the pools' own level rather than looking for them from a ledge.

    Returns {"pool", "rim", "dist", "far", "bearing", "drop", "dep", "clipped"}, or None
    when the mass sits at or above the horizon (`dep <= LAVA_DEP_MIN`). `rim` is the cell
    one step short of the pool along the bearing, at the level whose TOP face the water
    goes on -- exactly the argument `make_obsidian(x, y, z)` wants. `clipped` is True
    when the mass ran off the bottom of the readable frame (`bottom >= 0.85`, the hotbar
    cut): `dist` is then an upper bound and the lava may be nearer than it says.
    """
    try:
        pitch, yaw = float(pos["pitch"]), float(pos["yaw"])
        px0, py0, pz0 = float(pos["x"]), float(pos["y"]), float(pos["z"])
    except (KeyError, TypeError, ValueError):
        return None
    bearing, dep = lava_ray(pitch, yaw, cx, bottom)
    if dep <= LAVA_DEP_MIN:
        return None
    t = math.tan(math.radians(min(dep, LAVA_DEP_MAX)))
    drop = 0
    while True:
        dist = (MW.EYE + drop) / t
        if dist >= float(min_dist) or drop >= int(max_drop):
            break
        drop += 1
    dist = min(dist, LAVA_DIST_MAX)
    far = None
    if top is not None:
        dep_far = lava_ray(pitch, yaw, cx, top)[1]
        if dep_far > LAVA_DEP_MIN:
            far = min(LAVA_DIST_MAX, (MW.EYE + drop)
                      / math.tan(math.radians(min(dep_far, LAVA_DEP_MAX))))
    dx, dz = MW.facing(bearing)
    foot = math.floor(py0)
    pool = (math.floor(px0 + dist * dx), foot - 1 - drop, math.floor(pz0 + dist * dz))
    # One step short of the pool along the bearing, snapped to the axis so the rim is
    # always a face neighbour of the pool cell on OUR side of it. Its level: flush with
    # the pool when the pool lies in our own floor, otherwise the floor block at the
    # near edge of the pit -- a staged scene poured a sunk 3x3 pool from exactly there.
    ax, az = MW.axis_facing(bearing)
    rim = (pool[0] - ax, pool[1] if drop == 0 else foot - 1, pool[2] - az)
    return {"pool": pool, "rim": rim, "dist": dist, "far": far, "bearing": bearing,
            "drop": drop, "dep": dep, "clipped": float(bottom) >= 0.85}


#: The last lava sighting whose geometry was read (find_lava's stop, or the runner's
#: LAVA AHEAD guard with a bucket carried): pool cell, rim cell, where the avatar stood.
#: `make_obsidian()` and `mine_obsidian()` called WITHOUT coordinates use it, so the
#: cells never pass through the model's transcription -- one run read
#: "(-2992, 10, -5561)" out of the note, wrote (-2992, 10, -5560), and mined stone.
LAST_LAVA: dict[str, Any] | None = None


_SEQ = [0]


def _next_seq() -> int:
    _SEQ[0] += 1
    return _SEQ[0]


def remember_lava(cells: dict[str, Any], step: int, pos: dict[str, float],
                  source: str) -> None:
    global LAST_LAVA
    LAST_LAVA = {"pool": tuple(int(v) for v in cells["pool"]),
                 "rim": tuple(int(v) for v in cells["rim"]),
                 "dist": float(cells.get("dist") or 0.0), "step": int(step),
                 "at": (float(pos["x"]), float(pos["y"]), float(pos["z"])),
                 "source": source, "clipped": bool(cells.get("clipped", False)),
                 "seq": _next_seq()}


def lava_sentence(cells: dict[str, Any]) -> str:
    """The sentence that turns a lava sighting into the next call."""
    p, r = cells["pool"], cells["rim"]
    where = (f"about {cells['dist']:.0f} blocks off on bearing {cells['bearing']:.0f}"
             if not cells["clipped"] else
             f"{cells['dist']:.0f} blocks off AT MOST (it runs off the bottom of the "
             f"view, so it may be nearer) on bearing {cells['bearing']:.0f}")
    depth = ("" if not cells["drop"] else
             f" It is BELOW you -- about {cells['drop']} block(s) under the floor you "
             f"stand on, so you are looking down into it.")
    return (f"The lava is {where}: the pool's near cell is about {tuple(p)} (if the pool "
            f"lies lower than that, the lava -- and the obsidian after the pour -- is the "
            f"cell under it), the RIM "
            f"block to pour from is about {tuple(r)}.{depth} Both come from one frame's "
            f"geometry and are good to about a block: call "
            f"`make_obsidian({r[0]}, {r[1]}, {r[2]})` from where you stand (step 1-2 "
            f"blocks closer, never into it, if the pour is refused as out of reach), "
            f"then mine_obsidian on the pool cells with the diamond pickaxe.")


#: Never closer than this: the walk stops on the sighting frame and backs off if the
#: geometry says the pool is nearer. Two blocks is one walking tick of margin at 0.2
#: blocks/tick plus the 4-tick sampling gap.
FIND_MIN_DIST = 2.0
