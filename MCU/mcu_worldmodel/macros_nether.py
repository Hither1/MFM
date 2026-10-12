"""The obsidian -> portal -> Nether stretch of the dragon chain, as verified macros.

Why. After the iron pickaxe the dragon task asks for diamond gear, obsidian, a lit portal
and a trip to the Nether before any blaze or enderman can be fought. Every landed run
stopped at the diamond pickaxe: no run had ever poured water on lava, built a frame or
walked through a portal, and each of those is a geometry problem the model cannot do by
eye (where does the water source land? which face of which frame block do I click?
when am I "in" the portal?). These compose the coordinate macros of macros_world:

- `make_obsidian(x, y, z)`: pour a water bucket onto the top of the block at (x, y, z) --
  the rim block beside a lava pool -- so the water flows over the lava sources and turns
  them to obsidian, then scoop the water source back up from the cell above that block.
  Verified on the bucket swapping both ways.
- `mine_obsidian(x, y, z)`: look at the block, hold attack with the diamond pickaxe until
  `mine_block obsidian` moves (~190 ticks by pickaxe), sweep the drop.
- `build_portal_frame(dist)`: the 14-block obsidian outline (4 wide x 5 high, corners
  included so every block has a neighbour to build on) standing on the ground `dist`
  blocks ahead, across your facing; each placement verified, resumable.
- `light_portal(dist)`: flint_and_steel on the frame's bottom row, inside; verified on
  `use_item.flint_and_steel` and the purple portal pixels in the frame.
- `enter_portal(dist)`: walk into the frame's interior and stand still until the
  dimension changes -- detected on `location_stats.biome_id` (Nether biomes are 8 and
  170-173 in 1.16) and the coordinate jump -- then say where you are.

`vision.portal_fraction` is the purple band of a lit portal, measured in the frame the
stage saves. Nothing here reads a scoring rule; it is the game's own recipe for a portal.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from mcu_worldmodel import gui, macros, vision
from mcu_worldmodel import macros_world as MW

#: 1.16 Nether biome ids (nether_wastes, soul_sand_valley, crimson_forest, warped_forest,
#: basalt_deltas); the End is 9.
NETHER_BIOMES = {8, 170, 171, 172, 173}
END_BIOMES = {9}
#: Ticks a player must stand in a portal before it fires (4 s), plus the load.
PORTAL_WAIT = 160
#: Ticks for a water flow to drain after its source is scooped (5 s per block of
#: spread; the far edge of a 7-block spread is gone in ~100).
DRAIN_TICKS = 110
#: Purple/magenta of the portal block, as colour bands on the frame body.
_PORTAL_R = (90.0, 220.0)
_PORTAL_BR = (0.85, 2.2)      # b / r
_PORTAL_GR = (0.0, 0.62)      # g / r
PORTAL_FRAC_MIN = 0.004


def portal_fraction(frame) -> float:
    """Share of the frame body that is portal-purple."""
    if frame is None:
        return 0.0
    f = np.asarray(frame)
    if f.ndim != 3:
        return 0.0
    body = f[: int(f.shape[0] * 0.82)].astype(np.float32)
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    rr = np.maximum(r, 1.0)
    m = ((r >= _PORTAL_R[0]) & (r <= _PORTAL_R[1]) & (b / rr >= _PORTAL_BR[0])
         & (b / rr <= _PORTAL_BR[1]) & (g / rr <= _PORTAL_GR[1]) & (b > g + 25))
    return float(m.mean())


# -- where the lava is -------------------------------------------------------------

#: The camera's field of view: 70 degrees down the height (Minecraft's FOV setting is
#: the VERTICAL one) and ~102 across at 16:9, which is the same camera read the other way
#: -- tan(h/2) = (16/9) * tan(35) = 1.245, h = 102.3 (macros_world.FETCHW_HFOV, the tree
#: world's measurement, confirmed on the engine in a staged scene).
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
#: The cells of the last pour: mine_obsidian() aims at the pool cell as it was when the
#: water went out, not at whatever the guard re-sighted afterwards (one run: a
#: walk after the pour re-sighted the remaining lava with the poured rim as "pool",
#: and mine_obsidian() broke the rim's stone three times).
LAST_POUR: dict[str, Any] | None = None
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


# -- obsidian ----------------------------------------------------------------

#: The scoop-back's budget and floor, and the mining tick's. Breaking obsidian with a
#: diamond pickaxe takes ~188 ticks of UNBROKEN attack (a released button resets the
#: block's progress), plus the aim; under MINEOBS_MIN the call cannot finish.
SCOOP_TICKS = 120
#: The scoop walks up to this close to the source cell before pressing (one run:
#: 17 presses at 4.2 blocks took nothing; a staged scene scooped at 2-3).
SCOOP_NEAR = 3.2
SCOOP_MIN = 60
MINEOBS_MIN = 240
MINEOBS_MAX = 400
#: A camera correction larger than this while mining is done WITHOUT the attack key
#: (a swing at the wrong cell); under it the correction rides along with the swing.
MINEOBS_HOLD_TOL = 6.0
MINEOBS_AIM_TOL = 2.5


def _lava_cells_default(x, y, z, label: str) -> tuple[tuple[int, int, int] | None, str | None]:
    """(cell, error): the coordinates given, or the last sighting's when none are."""
    given = [v for v in (x, y, z) if v is not None]
    if given and len(given) < 3:
        return None, f"{label}: give all three of x, y, z, or none (the last sighting)."
    if given:
        try:
            return (math.floor(float(x)), math.floor(float(y)), math.floor(float(z))), None
        except (TypeError, ValueError):
            return None, f"{label}: bad coordinates {x!r}, {y!r}, {z!r}"
    if LAST_LAVA is None:
        return None, (f"{label}: no lava sighting on record yet -- find_lava(), or walk "
                      f"until the runner's LAVA AHEAD note names the cells, then call "
                      f"{label}() with no arguments (or with the x, y, z the note gives).")
    return None, ""          # the caller picks rim or pool from LAST_LAVA


#: Lava in the lower view that counts as seeing it (the guard fires at more).
LAVA_SEEN_FRAC = 0.01
#: Before the pour the avatar backs away from the pool: to at least this far from the
#: sighting's pool cell AND at least BACKOFF_MIN_MOVE blocks from where it stood, in at
#: most BACKOFF_TICKS. One run stood at the lip of a lake the guard had
#: put 3 blocks off ("at most"), poured, was carried off the ledge by the flow and
#: died in the lava 40 ticks later.
BACKOFF_STANDOFF = 3.5
BACKOFF_MIN_MOVE = 1.0
BACKOFF_TICKS = 60
#: mine_obsidian walks up to this many ticks to bring the cell within reach, and never
#: nearer than MINEOBS_APPROACH blocks of it (a cell that is still lava stays 4 away).
MINEOBS_WALK_TICKS = 40
MINEOBS_APPROACH = MW.REACH - 0.15


def _lava_now(info: dict) -> float:
    frame = info.get("pov") if isinstance(info, dict) else None
    if frame is None:
        return 0.0
    try:
        return float(vision.lava_fraction(np.asarray(frame)))
    except Exception:
        return 0.0


def _lava_in_evidence(info: dict) -> bool:
    """Lava in this frame, or a sighting the runner's frame classifier made (the guard
    or find_lava) -- not a pour by coordinates, which proves nothing."""
    if LAST_LAVA is not None and LAST_LAVA.get("source") in ("guard", "find_lava"):
        return True
    return _lava_now(info) >= LAVA_SEEN_FRAC


def make_obsidian(cur, info: dict, x: float | None = None, y: float | None = None,
                  z: float | None = None) -> tuple[list[dict[str, Any]], str]:
    """Pour water on top of the rim block beside the lava, wait for the flow to quench
    the sources, scoop the source back (walking back into reach if the flow pushed the
    avatar off), and wait for the spread to drain.

    Without coordinates the rim is the last sighting's (`LAST_LAVA`)."""
    if not gui.find_slots(info, "water_bucket"):
        return [], "make_obsidian: you carry no water_bucket (fill a bucket at water first)."
    rim, err = _lava_cells_default(x, y, z, "make_obsidian")
    if err:
        return [], err
    from_sighting = rim is None
    if rim is None:
        rim = LAST_LAVA["rim"]
    elif not _lava_in_evidence(info):
        # A pour by coordinates with no lava in view and no sighting by the frame is a
        # blind pour: three runs each tunnelled to a remembered rim
        # in the dark, poured on stone, lost the water and two of them died there.
        return [], (f"make_obsidian: no lava is in view ({100 * _lava_now(info):.0f}% of "
                    f"the lower view) and the runner has not sighted any -- a pour by "
                    f"coordinates would be blind. Get the lava INTO VIEW first (walk or "
                    f"tunnel toward it with the bucket carried until the LAVA AHEAD note "
                    f"names the pool and rim cells), then make_obsidian() with no "
                    f"arguments.")
    acts, note = MW.use_at(cur, info, rim[0], rim[1], rim[2], item="water_bucket",
                           face="above")
    if not acts:
        return [], note
    pool = LAST_LAVA["pool"] if from_sighting else rim
    global LAST_POUR
    LAST_POUR = {"pool": tuple(pool), "rim": tuple(rim), "seq": _next_seq(),
                 "bearing": (pool[0] - rim[0], pool[2] - rim[2])}
    # A sighting whose lava ran off the bottom of the view put the pool "at most" that
    # far: the avatar may be at the lip (one run), so only backing off is allowed. An
    # unclipped one is a measured distance: a far pool (one run: 8 blocks, the rim out of
    # reach) is approached to the standoff band instead.
    clipped = bool(LAST_LAVA.get("clipped", True)) if from_sighting else False
    back = macros.marker("_backoff", {"pool": list(pool), "t": 0, "n": BACKOFF_TICKS,
                                      "start": None, "last": None, "stall": 0,
                                      "approach": not clipped, "label": "make_obsidian"},
                         BACKOFF_TICKS)
    acts.insert(0, back)
    if not from_sighting:
        # A pour by coordinates (a KNOWN SITES rim, or the model's own reading) is a
        # sighting too: mine_obsidian() afterwards aims at THIS cell -- if it was the
        # rim, the rim breaks first and the obsidian behind it is next along the ray
        # (a staged scene); if the model named the lava cell itself, that cell is the obsidian
        # now. One run poured by coordinates and then had mine_obsidian()
        # refused for want of a sighting.
        from mcu_worldmodel.milestones import location
        pos = location(info) or {"x": rim[0] - 1.0, "y": rim[1] + 1.0, "z": rim[2] - 1.0}
        remember_lava({"pool": rim, "rim": rim, "dist": 0.0}, 0, pos, "pour")
    acts.append(macros.marker("_wait", {"t": 0, "n": 50, "label": "make_obsidian: the "
                                        "water flows over the lava"}, 50))
    # The source sits in the cell above the rim block. The scoop is closed-loop: the
    # flow that spread from the source pushes the avatar around (a staged scene: 4.6 blocks
    # of drift; two runs: the scoop refused as "out of reach" at 4.5-5.5
    # blocks and the source left flowing), so it walks back into reach and re-aims
    # every tick until the bucket reads water again.
    above = (rim[0], rim[1] + 1, rim[2])
    scoop = macros.marker("_scoop", {"cell": list(above), "t": 0, "n": SCOOP_TICKS,
                                     "phase": "walk", "presses": 0, "base_wb": None,
                                     "hold": 0, "label": "make_obsidian"}, SCOOP_TICKS)
    scoop["_min"] = SCOOP_MIN
    acts.append(scoop)
    acts.append(macros.marker("_wait", {"t": 0, "n": DRAIN_TICKS,
                                        "label": "make_obsidian: the water drains"},
                              DRAIN_TICKS))
    acts.append(macros.marker("_obsidiancheck", {"t": 0, "rim": list(rim)}, 4))
    return acts, (f"make_obsidian: standing off the pool at {BACKOFF_STANDOFF:.1f}-"
                  f"{BACKOFF_STANDOFF + 0.7:.1f} blocks first (backing away, or walking up "
                  f"to it when the sighting measured it further), then water onto the top "
                  f"of {rim}"
                  + (" (the last sighting's rim)" if from_sighting else "")
                  + f", then scooping the source back from {above} (walking back into "
                    f"reach if the flow pushes you), then waiting for the flow to drain")


@macros.tick("_wait", shrink="n")
def _wait_tick(agent, w: dict[str, Any], mk_act):
    w["t"] += 1
    if w["t"] >= w["n"]:
        return None
    return mk_act()


@macros.tick("_backoff", shrink="n", moving=True)
def _backoff_tick(agent, st: dict[str, Any], mk_act):
    """Face the pool and walk backwards until BACKOFF_STANDOFF blocks from it and
    BACKOFF_MIN_MOVE from where the avatar stood; a wall behind ends it early."""
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    px, py, pz = st["pool"]
    here = (float(pos["x"]), float(pos["z"]))
    if st["start"] is None:
        st["start"] = here
    d_pool = math.hypot(px + 0.5 - here[0], pz + 0.5 - here[1])
    moved = math.hypot(here[0] - st["start"][0], here[1] - st["start"][1])
    st["t"] += 1

    def _done(why: str):
        agent.memory.add_note(f"{st['label']}: backed off {moved:.1f} blocks to "
                              f"{d_pool:.1f} from the pool cell ({px}, {py}, {pz}){why}.")
        return None

    far = st.get("approach") and d_pool > BACKOFF_STANDOFF + 0.7
    if not far and d_pool >= BACKOFF_STANDOFF and (moved >= BACKOFF_MIN_MOVE
                                                   or st.get("approach")):
        return _done("")
    if st["t"] > st["n"]:
        return _done(" (out of ticks)")
    last = st.get("last")
    st["last"] = here
    if last is not None and st["t"] > 4:
        st["stall"] = st["stall"] + 1 if math.hypot(here[0] - last[0], here[1] - last[1]) < 0.03 else 0
        if st["stall"] >= 8:
            return _done(" -- something blocks the way" + (" up to it" if far else " back")
                         + "; pouring from here")
    _, yaw, _ = MW.angles_to(pos, (px + 0.5, py + 0.5, pz + 0.5))
    dy = MW.norm_yaw_delta(yaw, float(pos["yaw"]))
    if abs(dy) > 12.0:
        return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
    if far:
        # Closing on a measured pool: a walk, never a sprint, the heading held on it.
        return mk_act(forward=1, camera=[0.0, max(-10.0, min(10.0, dy))])
    return mk_act(back=1, camera=[0.0, max(-10.0, min(10.0, dy))])


@macros.tick("_scoop", shrink="n", moving=True)
def _scoop_tick(agent, st: dict[str, Any], mk_act):
    """Walk to within reach of the water source cell and press use on it with the empty
    bucket until the inventory reads a water_bucket again."""
    if agent._gui_open:
        agent._flush_tail(f"{st['label']}: a screen is open; close_inventory first.",
                          "scoop_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    wb = int(agent._cur_inv.get("water_bucket", 0))
    if st["base_wb"] is None:
        st["base_wb"] = wb
    if wb > st["base_wb"]:
        agent.cursor_stats["scoop_ok"] = agent.cursor_stats.get("scoop_ok", 0) + 1
        agent.memory.add_note(f"{st['label']}: the water source is back in the bucket "
                              f"({st['presses']} press(es), {st['t']} ticks).")
        return None
    st["t"] += 1
    cx, cy, cz = st["cell"]
    # The top of the source cell, as use_at(face="above") aims: the flow that spread
    # from it lies lower in the cells between, and an empty bucket on FLOWING water
    # scoops nothing (one run: 20 presses at the cell's centre, nothing;
    # the model's own use_at at the top face, one press).
    point = (cx + 0.5, cy + 0.8, cz + 0.5)     # under the 0.875 surface: the ray meets it inside the cell
    pitch, yaw, dist = MW.angles_to(pos, point)
    if st["t"] > st["n"]:
        agent._note_failure(st["label"])
        agent.memory.add_note(
            f"{st['label']}: the source was NOT scooped back ({st['presses']} press(es), "
            f"now {dist:.1f} blocks from ({cx}, {cy}, {cz})): it still flows there. Stand "
            f"within 3 blocks of it and use_at({cx}, {cy}, {cz}, item=\"bucket\", "
            f"face=\"above\"), or leave it -- the pour already did its work.")
        return None
    dy = MW.norm_yaw_delta(yaw, float(pos["yaw"]))
    dp = pitch - float(pos["pitch"])
    if dist > SCOOP_NEAR:
        # Walk toward the cell against the current, heading corrected every tick; no
        # sprint (a running jump over the rim would land in what was lava a moment
        # ago). A step in the way is climbed with a jump once the walk stalls:
        # One run poured from a tunnel one level under the rim, was
        # pushed 9 blocks back by the flow, and walked at the step for 120 ticks.
        st["phase"] = "walk"
        last = st.get("last_xz")
        here = (float(pos["x"]), float(pos["z"]))
        moved = math.hypot(here[0] - last[0], here[1] - last[1]) if last else 1.0
        st["last_xz"] = here
        st["stall"] = st.get("stall", 0) + 1 if moved < 0.05 else 0
        return mk_act(forward=1, jump=1 if st["stall"] >= 4 else 0,
                      camera=[max(-10.0, min(10.0, dp)), max(-15.0, min(15.0, dy))])
    if abs(dp) > MINEOBS_AIM_TOL or abs(dy) > MINEOBS_AIM_TOL:
        st["phase"] = "aim"
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    # Aimed and within reach: press use for two ticks, then let the inventory catch up.
    st["hold"] += 1
    if st["hold"] <= 2:
        if st["hold"] == 1:
            st["presses"] += 1
        return mk_act(use=1)
    if st["hold"] >= 6:
        st["hold"] = 0
    return mk_act()


@macros.tick("_obsidiancheck")
def _obsidiancheck_tick(agent, oc: dict[str, Any], mk_act):
    if oc["t"] < 3:
        oc["t"] += 1
        return mk_act()
    have_wb = agent._cur_inv.get("water_bucket", 0)
    agent.cursor_stats["obsidian_pours"] = agent.cursor_stats.get("obsidian_pours", 0) + 1
    pool = LAST_LAVA["pool"] if LAST_LAVA else None
    agent.memory.add_note(
        f"make_obsidian: done at the rim {tuple(oc['rim'])} -- every lava SOURCE the "
        f"water touched is obsidian now (flowing lava becomes cobblestone). "
        + ("The water is back in the bucket." if have_wb else
           "The water source was NOT scooped back (no water_bucket carried): it still "
           "flows there; use_at(the cell above the rim, item=\"bucket\") to take it.")
        + " Mine the obsidian with a DIAMOND pickaxe: `mine_obsidian()` with no "
          "arguments mines the sighting's pool cell"
        + (f" {pool}" if pool else "")
        + " (it takes ~190 ticks of unbroken swinging and must be FIRST in its plan).")
    return None


def mine_obsidian(cur, info: dict, x: float | None = None, y: float | None = None,
                  z: float | None = None, ticks: int = 300
                  ) -> tuple[list[dict[str, Any]], str]:
    """Hold attack on the obsidian block with the diamond pickaxe, the aim servoed onto
    the block's centre every tick, until `mine_block obsidian` moves; then sweep the
    drop. Without coordinates the block is the last sighting's pool cell."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel import macros_gui as MG

    if not gui.find_slots(info, "diamond_pickaxe"):
        return [], ("mine_obsidian: obsidian needs a DIAMOND pickaxe (any other tool "
                    "breaks it without a drop). Craft one first.")
    cell, err = _lava_cells_default(x, y, z, "mine_obsidian")
    if err:
        return [], err
    from_sighting = cell is None
    more: list[tuple[int, int, int]] = []
    if cell is None:
        same_site = (LAST_POUR is not None and math.dist(
            (LAST_POUR["pool"][0], LAST_POUR["pool"][2]),
            (LAST_LAVA["pool"][0], LAST_LAVA["pool"][2])) <= 2.5)
        if LAST_POUR is not None and (LAST_POUR["seq"] >= LAST_LAVA["seq"] or same_site):
            cell = LAST_POUR["pool"]
            bx, bz = LAST_POUR["bearing"]
            if (bx, bz) != (0, 0):
                more.append((cell[0] + bx, cell[1], cell[2] + bz))    # one further in
            if LAST_POUR["rim"] != cell:
                more.append(LAST_POUR["rim"])
        else:
            cell = LAST_LAVA["pool"]
    acts, hot, err = MG.ensure_hotbar(cur, info, "diamond_pickaxe", "mine_obsidian")
    if err:
        return [], err
    acts += P.equip_hotbar(hot + 1)
    n = max(MINEOBS_MIN, min(MINEOBS_MAX, int(ticks)))
    m = macros.marker("_mineobs", {"cell": list(cell), "t": 0, "n": n, "phase": "aim",
                                   "base_obs": None, "base_inv": None, "base_breaks": None,
                                   "held": 0, "label": "mine_obsidian",
                                   "more": [list(c) for c in more]}, n)
    m["_min"] = MINEOBS_MIN
    acts.append(m)
    # No drop sweep after the break: the emptied cell is a hole over the pool (one run fell
    # in one turn later); the note that follows says how to fill it and take the drop.
    return acts, (f"mine_obsidian: swinging the diamond pickaxe at {tuple(cell)}"
                  + ((" (the last pour's pool cell" + (f"; then {', '.join(str(c) for c in more)}"
                                                       if more else "") + ")")
                     if from_sighting and more else
                     (" (the last sighting's pool cell)" if from_sighting else ""))
                  + f" with the aim held on its centre, up to {n} ticks, until "
                    f"`mine_block obsidian` moves (about 190 ticks of unbroken attack); "
                    f"then the note says how to fill the hole and take the drop.")


@macros.tick("_mineobs", shrink="n")
def _mineobs_tick(agent, st: dict[str, Any], mk_act):
    if agent._gui_open:
        agent._flush_tail(f"{st['label']}: a screen is open; close_inventory first.",
                          "mineobs_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    mined = agent.stat_now("mine_block", "obsidian")
    have = int(agent._cur_inv.get("obsidian", 0))
    breaks = agent._log_breaks + agent._other_breaks
    if st["base_obs"] is None:
        st["base_obs"], st["base_inv"], st["base_breaks"] = mined, have, breaks
    cx, cy, cz = st["cell"]
    if mined - st["base_obs"] >= 1 or have > st["base_inv"]:
        agent.cursor_stats["obsidian_mined"] = agent.cursor_stats.get("obsidian_mined", 0) + 1
        # The cell is a HOLE over the pool now: one run (step 14294) walked
        # west across the one it had just emptied and burned to death with 5 obsidian.
        # On the map it is lava, and the note says to fill it from the rim.
        agent.grid.mark_lava(agent.step, (cx, cy, cz), None, 1.0)
        agent.memory.add_note(
            f"{st['label']}: OBSIDIAN BROKEN at ({cx}, {cy}, {cz}) after {st['t']} ticks "
            f"(mine_block obsidian +{mined - st['base_obs']:g}"
            + (f", obsidian +{have - st['base_inv']} in the inventory" if have > st["base_inv"]
               else "; the drop lies where the block was and BURNS if lava lies under it "
                    "-- the inventory count is the truth")
            + f"). That cell is now a HOLE over the pool: NEVER step on or across it. "
              f"From where you stand, place_at(x={cx}, y={cy}, z={cz}, item=\"cobblestone\", "
              f"face=<a side whose neighbour is solid>) fills it (a drop inside pops up onto "
              f"the block), then it is floor again. The portal needs 10: the pool's other "
              f"source cells are obsidian too, one mine_obsidian(x, y, z) each.")
        return None
    st["t"] += 1
    if st["t"] > st["n"]:
        agent._note_failure(st["label"])
        agent.memory.add_note(
            f"{st['label']}: no obsidian broke at ({cx}, {cy}, {cz}) in {st['n']} ticks "
            f"({breaks - st['base_breaks']:g} other block(s) broke). Either that cell is not "
            f"obsidian (the pour did not reach it: pour again from a rim nearer to it) or the "
            f"aim slid off (stand still on solid ground within 3 blocks and call it again).")
        return None
    # A block that is NOT obsidian broke under the crosshair. Once or twice that is the
    # rim: a pool one level down sits behind the rim block's top face from where the
    # pour was made, so the ray meets the rim first (a staged scene: stone in 12
    # ticks, then the obsidian behind it). The swing goes on, re-aimed. A third foreign
    # break means the cell is wrong or the pour made cobblestone; say so and stop.
    foreign = breaks - st["base_breaks"]
    if foreign >= st.get("foreign", 0) + 1 and st["phase"] == "mine":
        st["foreign"] = int(foreign)
        if foreign >= 3:
            nxt = (st.get("more") or [])
            if nxt:
                st["cell"] = list(nxt.pop(0))
                st["base_breaks"], st["foreign"] = breaks, 0
                agent.memory.add_note(
                    f"{st['label']}: three blocks broke at ({cx}, {cy}, {cz}) and none was "
                    f"obsidian; trying the next cell of the pour, {tuple(st['cell'])}.")
                st["phase"] = "aim"
                return mk_act()
            agent._note_failure(st["label"])
            agent.memory.add_note(
                f"{st['label']}: {foreign:g} blocks broke under the crosshair in {st['t']} "
                f"ticks and none was obsidian (mine_block obsidian did not move) -- "
                f"({cx}, {cy}, {cz}) is the wrong cell, or the pour turned it to cobblestone "
                f"(flowing lava). Look at the pool: obsidian is the black glossy block; call "
                f"mine_obsidian(x, y, z) on one, or make_obsidian again from a rim cell "
                f"beside still lava.")
            return None
        agent.memory.add_note(
            f"{st['label']}: a block in the way broke first after {st['t']} ticks (not "
            f"obsidian: the rim in front of the cell); swinging on at ({cx}, {cy}, {cz}).")
        st["phase"] = "aim"
        return mk_act()
    # A cell below the eye shows its TOP face; aiming at the centre of a cell that sits
    # behind another's top face hits the nearer block (a staged scene mined the rim instead).
    aim_y = cy + 0.9 if (float(pos["y"]) + MW.EYE > cy + 1) else cy + 0.5
    pitch, yaw, dist = MW.angles_to(pos, (cx + 0.5, aim_y, cz + 0.5))
    dp = pitch - float(pos["pitch"])
    dy = MW.norm_yaw_delta(yaw, float(pos["yaw"]))
    if dist > MINEOBS_APPROACH:
        # Walk it into reach (the pour backed the avatar off the pool), never nearer
        # than MINEOBS_APPROACH blocks of the cell -- if it is still lava that keeps
        # the avatar dry -- and not for longer than MINEOBS_WALK_TICKS.
        st["walk_t"] = st.get("walk_t", 0) + 1
        st["t"] -= 1                        # the walk is not mining time
        if st["walk_t"] > MINEOBS_WALK_TICKS:
            agent._note_failure(st["label"])
            agent.memory.add_note(
                f"{st['label']}: ({cx}, {cy}, {cz}) is {dist:.1f} blocks from your eye -- "
                f"out of reach (max {MW.REACH}) and the walk toward it stalled. go_to "
                f"within 3 blocks of it (on the rim, never into the pool) and call it "
                f"again.")
            return None
        st["phase"] = "aim"
        last = st.get("last_xz")
        here = (float(pos["x"]), float(pos["z"]))
        stalled = last is not None and math.hypot(here[0] - last[0], here[1] - last[1]) < 0.05
        st["last_xz"] = here
        st["stall"] = st.get("stall", 0) + 1 if stalled else 0
        return mk_act(forward=1, jump=1 if st["stall"] >= 4 else 0,
                      camera=[max(-10.0, min(10.0, dp)), max(-15.0, min(15.0, dy))])
    if st["phase"] == "aim":
        if abs(dp) <= MINEOBS_AIM_TOL and abs(dy) <= MINEOBS_AIM_TOL:
            st["phase"] = "mine"
            return mk_act(attack=1)
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    # Mining: the attack key stays down (a release resets the block's progress); small
    # corrections ride along with the swing, a large drift re-aims without it.
    if abs(dp) > MINEOBS_HOLD_TOL or abs(dy) > MINEOBS_HOLD_TOL:
        st["phase"] = "aim"
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    st["held"] += 1
    return mk_act(attack=1, camera=[max(-3.0, min(3.0, dp)), max(-3.0, min(3.0, dy))])


# -- finding the lava in the first place -------------------------------------------

# Why this exists. Fifteen second-half arms (a kit with the diamond milestones already
# credited and a water bucket in the pack) sat at 13/24 for thousands of steps: four
# reached y <= 15 and NOT ONE ever met lava, so make_obsidian was never called and
# milestone 14 was never taken. Digging down is solved (dig_down/stair_down); what was
# missing is the horizontal search at depth, and a sighting the model can ACT on -- a
# note that names the cell to pour on, not "there is lava somewhere ahead".
#
# The search: tunnel a straight leg, sample vision.lava_fraction as the TARGET (the
# runner's lava guard treats the same reading as a hazard), turn 90 degrees when a leg
# finds nothing, stop on the first sighting well short of the pool and say where it is.

#: The level to search at. Lava lakes are common at y 5-10 in 1.16, and a tunnel at 11
#: looks down on them; 11 is also where strip mining for diamond already puts the agent.
FIND_LAVA_Y = 11.0
#: A leg of tunnel before turning 90 degrees, and the walk's pitch (the same 8 degrees
#: explore_nether walks at: the lower 65% band then covers the floor from ~3 blocks out).
FIND_LEG = 40
FIND_PITCH, FIND_PITCH_LAVA = 8.0, 28.0
#: The sighting threshold, EXPLORE_LAVA_WALK's: 2% of the lower view is a pool several
#: blocks off (a staged scene: a trench 4 blocks ahead read 4.5% at pitch 8), while every
#: archived lava-free underground frame read <= 0.002.
FIND_SEEN = 0.02
#: Never closer than this: the walk stops on the sighting frame and backs off if the
#: geometry says the pool is nearer. Two blocks is one walking tick of margin at 0.2
#: blocks/tick plus the 4-tick sampling gap.
FIND_MIN_DIST = 2.0
#: ...and no further than this before the note is written: the pour goes on the RIM
#: block, which has to be inside the 4.4-block reach, and a big lake is sighted from 8+.
#: So a distant sighting is closed on -- sneaking, re-reading every tick, never past
#: FIND_MIN_DIST -- for at most FIND_APPROACH ticks, and only then is the note written.
#: On the engine (a staged scene) a 3x3 pool crosses FIND_SEEN at about 3 blocks, so this
#: fires for lakes rather than for pools.
FIND_POUR_DIST = 3.5
FIND_APPROACH = 80
#: Ticks of zero progress that read as a wall to tunnel through.
FIND_STUCK = 6
#: Ticks per block of tunnel, for sizing the budget note (the mining cycle's ~18 ticks
#: per stone block plus the walk).
FIND_TICKS_PER_BLOCK = 22


#: Under this many ticks the search does not start: a leg tunnels ~40 ticks a block, so
#: a shrunk tail buys 4-5 blocks and no sighting (one run: three calls of
#: 162-198 ticks on the tails of 400-tick plans, nothing found).
FINDLAVA_MIN_TICKS = 250


def find_lava(cur, info: dict, n: int = 600, y: float = FIND_LAVA_Y,
              leg: int = FIND_LEG) -> tuple[list[dict[str, Any]], str]:
    """Tunnel at depth looking FOR lava, and name the cell to pour water on when it
    comes into view."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "find_lava: no position yet; act once and call it again."
    n = max(FINDLAVA_MIN_TICKS, min(1500, int(n)))     # a small model-chosen n is raised
    leg = max(8, min(120, int(leg)))
    try:
        y_t = float(y)
    except (TypeError, ValueError):
        y_t = FIND_LAVA_Y
    pick = next((p for p in _PICKS if gui.find_slots(info, p)), None)
    if not pick:
        return [], ("find_lava: you carry no pickaxe -- the search tunnels through stone. "
                    "Craft one first.")
    acts, err = MW._prep_item(cur, info, pick, "find_lava")
    if err:
        return [], err
    down = int(round(float(pos["y"]) - y_t))
    stairs = min(20, down) if down >= 2 else 0
    if stairs:
        acts += P.stair_down(depth=stairs, ore_watch=True)
    st = {"n": n, "t": 0, "leg": leg, "legs": 0, "turns": 0, "phase": "walk",
          "phase_t": 0, "yaw_t": MW.norm_yaw(float(pos["yaw"])), "start": None,
          "leg_from": None, "total": 0.0, "lava": 0.0, "stuck": 0, "last": None,
          "broken": 0, "base_breaks": None, "y0": None, "hits": 0, "approach": 0,
          "bucket": bool(gui.find_slots(info, "water_bucket"))}
    acts.append(macros.marker("_findlava", st, n))
    acts[-1]["_min"] = FINDLAVA_MIN_TICKS      # whole or not at all (procedures.shrink_marker)
    return acts, ("find_lava: "
                  + (f"a {stairs}-block staircase down to about y {y_t:.0f} first, then " if stairs else "")
                  + f"tunnelling in {leg}-block legs (turning 90 degrees after each) for "
                    f"up to {n} ticks, watching the lower view for lava. It STOPS on the "
                    f"first sighting, at least {FIND_MIN_DIST:.0f} blocks short of the "
                    f"pool, and names the rim cell for make_obsidian."
                  + ("" if st["bucket"] else " (You carry no water_bucket: fetch_water "
                                             "first, or the sighting cannot be used yet.)"))


def _findlava_finish(agent, st: dict[str, Any], why: str, flush: bool = False) -> None:
    pos = agent._cur_pos or {}
    sx, sz = st["start"] or (pos.get("x", 0.0), pos.get("z", 0.0))
    walked = math.hypot(pos.get("x", 0.0) - sx, pos.get("z", 0.0) - sz)
    if st["leg_from"]:                      # the leg in progress counts too
        st["total"] += math.hypot(pos.get("x", 0.0) - st["leg_from"][0],
                                  pos.get("z", 0.0) - st["leg_from"][1])
        st["leg_from"] = None
    agent.cursor_stats["findlava_runs"] = agent.cursor_stats.get("findlava_runs", 0) + 1
    agent.cursor_stats["findlava_blocks"] = (
        agent.cursor_stats.get("findlava_blocks", 0) + int(max(0.0, st["total"])))
    note = (f"find_lava: {st['total']:.0f} blocks of tunnel in {st['legs'] + 1} leg(s), "
            f"{st['broken']} block(s) broken, {st['t']} ticks; now at "
            f"({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, {pos.get('z', 0):.0f}) "
            f"facing yaw {pos.get('yaw', 0):.0f}, {walked:.0f} blocks from where the "
            f"search started. {why}")
    if flush:
        agent._flush_tail(note, "findlava_stops")
    else:
        agent.memory.add_note(note)


def _findlava_measure(agent, pitch: float) -> tuple[float, float, float, float]:
    """`vision.lava_view` read from one degree below the horizon rather than the fixed
    35% line: the search tilts its view down to put the near floor in the band, and at
    pitch 28 a pool 7 blocks off sits at the 29% line -- above the fixed cut, i.e.
    invisible to the reading that was taken to find it."""
    from mcu_worldmodel import vision

    frame = agent._last_pov
    if frame is None:
        return 0.0, 0.0, 0.0, 0.0
    rows_from = min(0.55, max(0.10, 0.5 - float(pitch) / LAVA_VFOV + 0.012))
    return vision.lava_view(np.asarray(frame), rows_from=rows_from)


def _findlava_sight(agent, st: dict[str, Any], pos: dict[str, float]) -> None:
    """Stop on the sighting: save the frame, name the pool and the rim, say the call."""
    frame = agent._last_pov
    frac, cx, bottom, top = _findlava_measure(agent, float(pos.get("pitch", 0.0)))
    agent.cursor_stats["findlava_seen"] = agent.cursor_stats.get("findlava_seen", 0) + 1
    data = agent._encode_pov(agent._last_pov, agent.step) if frame is not None else None
    rel = agent.memory.save_frame(agent.step, data, suffix="_lava") if data else None
    cells = lava_cells(pos, cx, bottom, top=top, min_dist=FIND_MIN_DIST) if frac else None
    if cells is None:
        why = (f"LAVA FOUND: it fills {100 * max(frac, st['lava']):.0f}% of the lower "
               f"view but sits at or above the horizon -- a lava FALL down a wall, not a "
               f"pool at your feet. Do not walk into it. Look down (look_abs(pitch=25)) "
               f"and call find_lava again to place its floor pool.")
    else:
        remember_lava(cells, agent.step, pos, "find_lava")
        why = (f"LAVA FOUND: it fills {100 * max(frac, st['lava']):.0f}% of the lower "
               f"view. " + lava_sentence(cells)
               + (" You carry a water_bucket, so the pour can happen now."
                  if st["bucket"] else
                  " You carry NO water_bucket: fetch_water first, then come back to this"
                  " spot and pour.")
               + " Do NOT walk any closer: lava ends a run in seconds, and the walk "
                 "already stopped with the pool ahead of you.")
    if rel:
        why += f" The frame is saved at {rel} and attached to your next turn."
    _findlava_finish(agent, st, why, flush=True)


@macros.tick("_findlava", shrink="n", moving=True)
def _findlava_tick(agent, st: dict[str, Any], mk_act):
    """One tick of the search: walk the leg, tunnel a wall, stop on lava.

    The shape is `_nexplore_tick`'s (walk, and when progress stops, cut the foot block
    then the eye block at the mining cycle's own pitches), with the lava reading turned
    around: there it is the hazard to sneak past, here it is the thing being looked for.
    """
    if agent._gui_open:
        agent._flush_tail("find_lava: a screen is open; movement and swings do nothing "
                          "in the world while it is. close_inventory first.",
                          "findlava_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    breaks = agent._log_breaks + agent._other_breaks
    if st["start"] is None:
        st["start"] = (pos["x"], pos["z"])
        st["leg_from"] = (pos["x"], pos["z"])
        st["y0"] = pos["y"]
        st["base_breaks"] = breaks
        if st["n"] < FINDLAVA_MIN_TICKS:
            # only the runner's step-cap shrink gets here (the compile raises a small n)
            agent.cursor_stats["findlava_not_started"] = (
                agent.cursor_stats.get("findlava_not_started", 0) + 1)
            _findlava_finish(agent, st, f"NOT STARTED: only {st['n']} ticks were available "
                                        f"(the plan's remaining budget) and a search needs "
                                        f"{FINDLAVA_MIN_TICKS}+ -- put find_lava FIRST in the "
                                        f"next plan, with n=600 or more.", flush=True)
            return None
    st["t"] += 1
    if st["t"] > st["n"]:
        _findlava_finish(
            agent, st,
            f"No lava came into view. Lava lakes are common at y 5-10 but sparse "
            f"sideways: move 30+ blocks from here (travel, or go_to a point) and call "
            f"find_lava() again, or try another level (y 8-12). Each call covers about "
            f"{st['n'] // FIND_TICKS_PER_BLOCK} blocks of tunnel.")
        return None
    if st["y0"] - pos["y"] > 4.0:
        _findlava_finish(
            agent, st, f"STOPPED: you dropped {st['y0'] - pos['y']:.0f} blocks -- a hole "
                       f"or a cave opened under the tunnel. Look around before walking "
                       f"on; do not jump down a shaft you cannot climb back out of.",
            flush=True)
        return None

    # -- the reading, every 4th tick (every 2nd once any lava shows) -----------------
    if st["t"] % (2 if st["lava"] > 0.0 else 4) == 0 and agent._last_pov is not None:
        st["lava"] = _findlava_measure(agent, float(pos["pitch"]))[0]
        # Entering `close` once: re-entering it on the next sample would reset its own
        # settle counter every other tick and the phase would never finish.
        if st["lava"] >= FIND_SEEN and st["phase"] != "close":
            st["hits"] += 1
            st["phase"], st["phase_t"] = "close", 0

    # -- heading: a large yaw error is corrected standing still ----------------------
    dy = MW.norm_yaw_delta(st["yaw_t"], pos["yaw"])
    if abs(dy) > 10.0 and st["phase"] != "close":
        st["stuck"] = 0
        return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])

    ph = st["phase"]
    if ph == "close":
        # Tilt down so the near floor is inside the measured band, read the geometry, and
        # settle at pouring range: the water goes on the rim block, which has to be within
        # the 4.4-block reach, and a sighting is made from 6-8 blocks out. So the walk
        # closes to FIND_POUR_DIST -- carefully, sneaking, re-reading every tick,
        # never below FIND_MIN_DIST -- and only then writes the note, so the
        # `make_obsidian(rim)` it names can be run from where the avatar is standing.
        st["phase_t"] += 1
        dp = FIND_PITCH_LAVA - pos["pitch"]
        if abs(dp) > 3.0 and st["phase_t"] <= 8:
            return mk_act(camera=[max(-20.0, min(20.0, dp)), 0.0])
        if st["phase_t"] <= 9:
            return mk_act()                      # one tick for the frame to catch up
        frac, cx, bottom, top = _findlava_measure(agent, float(pos["pitch"]))
        cells = lava_cells(pos, cx, bottom, top=top,
                           min_dist=FIND_MIN_DIST) if frac else None
        if cells is not None and (cells["dist"] < FIND_MIN_DIST or cells["clipped"]):
            if st["phase_t"] <= 40:
                # Sneak backwards: never a step toward the pool, never a jump.
                return mk_act(back=1, sneak=1)
        elif (cells is not None and cells["dist"] > FIND_POUR_DIST
                and st["approach"] < FIND_APPROACH):
            st["approach"] += 1
            dyaw = MW.norm_yaw_delta(cells["bearing"], pos["yaw"])
            return mk_act(forward=1, sneak=1,
                          camera=[max(-4.0, min(4.0, dp)), max(-6.0, min(6.0, dyaw))])
        _findlava_sight(agent, st, pos)
        return None

    if ph == "walk":
        prog = math.hypot(pos["x"] - st["leg_from"][0], pos["z"] - st["leg_from"][1])
        if prog >= st["leg"]:
            st["total"] += prog
            st["legs"] += 1
            st["leg_from"] = (pos["x"], pos["z"])
            st["yaw_t"] = MW.norm_yaw(st["yaw_t"] + 90.0)
            st["stuck"], st["last"] = 0, None
            agent.cursor_stats["findlava_turns"] = (
                agent.cursor_stats.get("findlava_turns", 0) + 1)
            return mk_act()
        careful = st["lava"] > 0.0
        dp = (FIND_PITCH_LAVA if careful else FIND_PITCH) - pos["pitch"]
        last = st.get("last")
        moved = math.hypot(pos["x"] - last[0], pos["z"] - last[1]) if last else None
        st["last"] = (pos["x"], pos["z"])
        if moved is not None and moved < 0.03:
            st["stuck"] += 1
        else:
            st["stuck"] = 0
        if st["stuck"] >= FIND_STUCK:
            st["stuck"] = 0
            st["phase"], st["phase_t"], st["base_breaks"] = "foot", 0, breaks
            return mk_act()
        # No sprint and no jump with any lava in view: a jump carries the avatar over an
        # edge before the next frame is read (explore_nether's measurement).
        return mk_act(forward=1, sprint=0 if careful else 1, jump=0 if careful else 1,
                      camera=[max(-6.0, min(6.0, dp)), max(-6.0, min(6.0, dy))])

    # -- tunnelling: the foot block, then the eye block, then walk again (the mining
    # cycle's pitches, agent._mfwd_tick: 35 then 8) --------------------------------
    target = 35.0 if ph == "foot" else 8.0
    dp = target - pos["pitch"]
    st["phase_t"] += 1
    if abs(dp) > 4.0 and st["phase_t"] <= 12:
        return mk_act(camera=[max(-20.0, min(20.0, dp)), 0.0])
    if breaks > st["base_breaks"] + 0.5:
        st["broken"] += 1
        st["base_breaks"] = breaks
        st["phase"], st["phase_t"] = ("eye" if ph == "foot" else "walk"), 0
        return mk_act()
    if st["phase_t"] > 34:
        st["phase"], st["phase_t"] = ("eye" if ph == "foot" else "walk"), 0
        return mk_act()
    return mk_act(attack=1)


# -- the portal frame ----------------------------------------------------------

def _frame_cells(pos: dict[str, float], dist: int
                 ) -> tuple[list[tuple[int, int, int, str]], tuple[int, int], tuple[int, int]]:
    """The 14 outline cells of a 4x5 frame `dist` ahead across the facing, in build
    order with the face each is placed against. Returns (targets, (dx, dz), (px, pz))."""
    bx, by, bz = MW.block_of(pos)
    dx, dz = MW.axis_facing(pos["yaw"])
    px, pz = dz, -dx                        # to the right
    # columns k = -1 .. 2 (4 wide, centred a little left of the facing line)
    ks = [-1, 0, 1, 2]

    def cell(k: int, h: int) -> tuple[int, int, int]:
        return (bx + dx * dist + px * k, by + h, bz + dz * dist + pz * k)

    side = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}
    left_face = side[(px, pz)]      # the face of a cell toward the column on its left
    out: list[tuple[int, int, int, str]] = []
    for k in ks:                                     # bottom row on the ground
        out.append((*cell(k, 0), "below"))
    for h in (1, 2, 3):                              # the two columns
        out.append((*cell(ks[0], h), "below"))
        out.append((*cell(ks[-1], h), "below"))
    right_face = side[(-px, -pz)]   # the face of a cell toward the column on its right
    out.append((*cell(ks[0], 4), "below"))           # top row: corners first
    out.append((*cell(ks[-1], 4), "below"))
    out.append((*cell(ks[1], 4), left_face))         # then inward: each against ITS
    out.append((*cell(ks[2], 4), right_face))        # nearest corner (the far one's
    return out, (dx, dz), (px, pz)                   # plane is behind the near block)


def build_portal_frame(cur, info: dict, item: str = "obsidian", dist: int = 2
                       ) -> tuple[list[dict[str, Any]], str]:
    """The 14-obsidian outline of a nether portal, `dist` blocks ahead, across your
    facing, standing on the ground. Resumable: a filled cell is skipped as refused."""
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "build_portal_frame: no position yet."
    dist = max(2, min(3, int(dist)))
    have = sum(q for _, q in gui.find_slots(info, item))
    bx, by, bz = MW.block_of(pos)
    # Resuming: a frame planned from this spot keeps its ground level and its cells,
    # whatever height the avatar's pillar has reached since.
    lf = LAST_FRAME
    resumed = bool(lf) and math.dist((lf["spot"][0], lf["spot"][1]),
                                     (bx + 0.5, bz + 0.5)) < 1.0 and lf["dist"] == dist
    if resumed:
        targets = [tuple(t) for t in lf["targets"]]
        # Only a frame that has blocks down is resumed (a planned-but-never-run frame
        # is re-planned from the current ground).
        resumed = bool(MW.remembered("build_portal_frame", targets))
    if resumed:
        by = int(lf["ground_y"])
        dx, dz = tuple(lf["facing"])
    else:
        targets, (dx, dz), _ = _frame_cells(pos, dist)
    done = MW.remembered("build_portal_frame", targets)
    need = 10 - sum(1 for t in targets if tuple(t[:3]) in done and t in
                    (targets[1], targets[2]) + tuple(targets[4:10]) + (targets[12], targets[13]))
    if have < max(0, need):
        return [], (f"build_portal_frame: {have} {item} carried; a frame needs 10 "
                    f"(without corners) and this macro places 14 (with corners, so "
                    f"every block has a neighbour to build on). Get 14, or 10 plus 8 "
                    f"cobblestone in the hotbar.")
    spot = [bx + 0.5, bz + 0.5]
    corners = [targets[0], targets[3], targets[10], targets[11]]
    inner = [t for t in targets if t not in corners]
    key = MW.build_key("build_portal_frame", targets)
    MW.LAST_BUILDS.setdefault(key, {"placed": []})
    cur_lift = max(0, int(round(pos["y"] - by)))
    lift_item = next((f for f in ("cobblestone", "dirt", "stone", "netherrack",
                                  "oak_planks", "andesite", "diorite", "granite")
                      if MW._hotbar_of(info, f) is not None), None)
    from mcu_worldmodel import procedures as P

    def pillar(n: int) -> dict:
        return macros.marker("_pillar", {"item": lift_item, "target": n, "placed": 0,
                                         "phase": "look", "t": 0, "tries": 0,
                                         "y_jump": None, "budget": n * 24 + 30,
                                         "used": 0}, n * 24 + 30)

    def rows(lo: int, hi: int, cells):
        return [t for t in cells if lo <= t[1] - by <= hi]

    if lift_item is None or MW._hotbar_of(info, lift_item) is None:
        return [], ("build_portal_frame: the upper rows can only be built from higher "
                    "up -- keep 4 cobblestone (or dirt) in your HOTBAR to stand on.")
    def remaining(cells):
        return [t for t in cells if tuple(t[:3]) not in done]

    if have >= 14 or (resumed and lf.get("mode") == "full"):
        # Every row's top faces must sit 1.62 below the eye when it is built (a
        # grazing view lands blocks one cell forward): row h is built h blocks up,
        # one pillar block per row on the hotbar filler. The pillar stays. A plan
        # holds ~400 ticks, so this is two calls: the second resumes from the pillar
        # top with the same cells and pillars only what is still missing.
        acts, err = MW._prep_item(cur, info, item, "build_portal_frame")
        if err:
            return [], err
        hot_o = MW._hotbar_of(info, item)
        hot_f = MW._hotbar_of(info, lift_item)
        solid = [list(c) for c in done]
        lifted = cur_lift
        for lo, hi, want in ((0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)):
            part = remaining(rows(lo, hi, targets))
            if not part:
                continue
            if want > lifted:
                acts += P.equip_hotbar(hot_f + 1)
                acts.append(pillar(want - lifted))
                acts += P.equip_hotbar((hot_o if hot_o is not None else 0) + 1)
                lifted = want
            acts.append(MW._build_marker(part, item, [spot] * len(part),
                                         "build_portal_frame", floor_y=by,
                                         solid=list(solid), key=key))
            solid += [list(t[:3]) for t in part]
        mode = "full"
    else:
        # 10-13 obsidian: the four corners are built from a filler block (the portal
        # does not need them, the BUILD does -- the top row and the columns have no
        # other neighbour to be placed against). Both stacks must sit in the hotbar,
        # because the two builds alternate: bottom corners, then the 8 lower frame
        # blocks, then the top corners, then the 2 top blocks.
        filler = lift_item
        if MW._hotbar_of(info, item) is None:
            return [], (f"build_portal_frame: put the {item} in your hotbar first (both "
                        f"it and the filler {filler} are selected in turn).")
        if sum(q for _, q in gui.find_slots(info, filler)) < 8:
            return [], (f"build_portal_frame: with {have} {item} the four corners and the "
                        f"two 2-block pillars need 8 {filler}; you carry fewer.")
        hot_o, hot_f = MW._hotbar_of(info, item), MW._hotbar_of(info, filler)
        acts = []
        lift_item = filler
        solid = [list(c) for c in done]
        lifted = cur_lift
        # (row range, cells, item, lift wanted before it)
        phases = [((0, 0), corners, filler, 0), ((0, 0), inner, item, 0),
                  ((1, 1), inner, item, 1), ((2, 2), inner, item, 2),
                  ((3, 3), inner, item, 3),
                  ((4, 4), corners, filler, 4), ((4, 4), inner, item, 4)]
        for (lo, hi), cells, what, want in phases:
            part = remaining(rows(lo, hi, cells))
            if not part:
                continue
            if want > lifted:
                acts += P.equip_hotbar(hot_f + 1)
                acts.append(pillar(want - lifted))
                lifted = want
            acts += P.equip_hotbar((hot_f if what == filler else hot_o) + 1)
            acts.append(MW._build_marker(part, what, [spot] * len(part),
                                         "build_portal_frame", floor_y=by,
                                         solid=list(solid), key=key))
            solid += [list(t[:3]) for t in part]
        mode = "filler"
    inside = (bx + dx * dist, by + 1, bz + dz * dist)
    LAST_FRAME.clear()
    LAST_FRAME.update({"bottom_inside": targets[1][:3], "inside": inside, "spot": spot,
                       "ground_y": by, "dist": dist, "targets": [list(t) for t in targets],
                       "facing": [dx, dz], "mode": mode})
    if not acts:
        return [], "build_portal_frame: every cell of this frame is already placed."
    return acts, (f"build_portal_frame: {len(targets) - len(done)} cells to place "
                  f"({len(done)} already there) in the plane {dist} ahead "
                  f"across yaw {pos['yaw']:.0f}; the portal's inside bottom cells are "
                  f"{inside} and {(inside[0] + (dz), inside[1], inside[2] - dx)}. A plan "
                  f"holds ~400 ticks: when the note says the budget ran out, call "
                  f"build_portal_frame again from the same spot -- it continues.")


#: The last frame compiled by build_portal_frame: its bottom-inside cell, so that
#: light_portal / enter_portal called from the pillar top (3-4 blocks higher than the
#: ground the frame was planned from) address the same frame.
LAST_FRAME: dict[str, Any] = {}


def _bottom_inside(pos: dict[str, float], dist: int) -> tuple[int, int, int]:
    lf = LAST_FRAME.get("bottom_inside")
    if lf and math.dist((pos["x"], pos["z"]), (lf[0] + 0.5, lf[2] + 0.5)) < 8.0:
        return tuple(lf)
    targets, _, _ = _frame_cells(pos, dist)
    return targets[1][:3]


def light_portal(cur, info: dict, dist: int = 2) -> tuple[list[dict[str, Any]], str]:
    """flint_and_steel on the top of the frame's bottom row, inside the frame."""
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "light_portal: no position yet."
    if not gui.find_slots(info, "flint_and_steel"):
        return [], "light_portal: you carry no flint_and_steel (1 iron ingot + 1 flint)."
    dist = max(2, min(3, int(dist)))
    bottom_inside = _bottom_inside(pos, dist)  # column k=0 of the bottom row
    ground = bottom_inside[1]
    lift = max(0, int(round(pos["y"] - ground)))
    if lift >= 2:
        # From the pillar top the bottom block is out of reach; fire placed INSIDE the
        # frame anywhere lights it. Click the left column's inner face at row
        # lift-2 (rows 1-3; the top row hides row 3 from a 4-block pillar): the ray
        # passes the interior above it and the fire lands in the interior cell.
        h = max(1, min(2, lift - 2))
        cell = (bottom_inside[0], ground + h, bottom_inside[2])
        dx, dz = (tuple(LAST_FRAME.get("facing")) if LAST_FRAME.get("facing")
                  else MW.axis_facing(pos["yaw"]))
        px, pz = dz, -dx
        face = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(px, pz)]
        acts, note = MW.use_at(cur, info, cell[0], cell[1], cell[2],
                               item="flint_and_steel", face=face)
        where = f"the inside face of the frame's left column at {cell}"
    else:
        cell = bottom_inside
        acts, note = MW.use_at(cur, info, cell[0], cell[1], cell[2],
                               item="flint_and_steel", face="above")
        where = f"top of {cell} (inside the frame)"
    if not acts:
        return [], note
    acts.append(macros.marker("_portalcheck", {"t": 0, "cell": list(cell)}, 6))
    return acts, f"light_portal: fire on {where}"


@macros.tick("_portalcheck")
def _portalcheck_tick(agent, pc: dict[str, Any], mk_act):
    if pc["t"] < 5:
        pc["t"] += 1
        return mk_act()
    frac = portal_fraction(agent._last_pov)
    if frac >= PORTAL_FRAC_MIN:
        agent.cursor_stats["portals_lit"] = agent.cursor_stats.get("portals_lit", 0) + 1
        agent.memory.add_note(
            f"light_portal: the portal is LIT ({100 * frac:.1f}% of the view is portal "
            f"purple). enter_portal walks in and waits for the Nether.")
    else:
        agent._note_failure("light_portal")
        agent.memory.add_note(
            "light_portal: no portal purple in the view after the fire. Either the "
            "frame is not a closed 4x5 obsidian rectangle (check every column and the "
            "top row with build_portal_frame again -- filled cells are skipped), or the "
            "fire went on the wrong block: it must burn INSIDE the frame, on top of a "
            "bottom frame block.")
    return None


def enter_portal(cur, info: dict, dist: int = 2, x: float | None = None,
                 z: float | None = None) -> tuple[list[dict[str, Any]], str]:
    """Walk into the frame's inside cell and stand still until the dimension changes."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "enter_portal: no position yet."
    acts: list[dict[str, Any]] = []
    if x is None or z is None:
        dist = max(2, min(3, int(dist)))
        cell = _bottom_inside(pos, dist)
        x, z = cell[0] + 0.5, cell[2] + 0.5
        ground = cell[1]
        if pos["y"] > ground + 1.5:
            # Still up the building pillar: walking straight at the frame lands on
            # its top row (a staged scene: "standing in the cell" five blocks
            # up), and stepping off BACKWARD leaves the pillar between you and the
            # portal (the next pass: "go_to blocked 2.8 blocks short"). Step off to
            # the SIDE, then walk in at ground level around the pillar.
            dx, dz = (tuple(LAST_FRAME.get("facing")) if LAST_FRAME.get("facing")
                      else MW.axis_facing(pos["yaw"]))
            px, pz = dz, -dx
            side = (pos["x"] + px * 1.8, pos["z"] + pz * 1.8)
            acts += P.look_abs(yaw=math.degrees(math.atan2(-px, pz)), ticks=20)
            acts += P.repeat(P.act(forward=1), 12)
            acts += P.go_to(side[0], side[1], within=0.7, n=60)
    acts += P.go_to(float(x), float(z), within=0.6, n=120)
    acts.append(macros.marker("_dimcheck", {"t": 0, "n": PORTAL_WAIT, "x": float(x),
                                            "z": float(z), "biome0": None, "pos0": None},
                              PORTAL_WAIT))
    return acts, f"enter_portal: stepping into ({x:.1f}, {z:.1f}) and waiting for the Nether"


def _biome(agent) -> int | None:
    loc = (agent.ledger._prev or {}).get("location_stats") or {}
    v = loc.get("biome_id")
    try:
        return int(v.item()) if hasattr(v, "item") else int(v)
    except (TypeError, ValueError):
        return None


def dimension_of(biome: int | None) -> str:
    if biome in NETHER_BIOMES:
        return "the Nether"
    if biome in END_BIOMES:
        return "the End"
    return "the Overworld"


@macros.tick("_dimcheck", shrink="n")
def _dimcheck_tick(agent, dc: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    if dc["biome0"] is None:
        dc["biome0"] = _biome(agent)
        dc["pos0"] = (pos["x"], pos["y"], pos["z"])
    b = _biome(agent)
    jumped = math.dist(dc["pos0"], (pos["x"], pos["y"], pos["z"])) > 12.0
    if (b is not None and b != dc["biome0"] and dimension_of(b) != dimension_of(dc["biome0"])) \
            or jumped:
        # `biome_id` reads 0 in both dimensions in this engine (a staged scene),
        # so the coordinate jump is the signal: the Overworld's x/z divided by 8
        # means the Nether, multiplied by 8 means the way back.
        x0, z0 = dc["pos0"][0], dc["pos0"][2]
        shrank = abs(pos["x"]) < abs(x0) / 2.0 + 8 and abs(pos["z"]) < abs(z0) / 2.0 + 8
        where = (dimension_of(b) if (b is not None and b != dc["biome0"]) else
                 ("the Nether" if shrank else "the Overworld"))
        agent.cursor_stats["portal_trips"] = agent.cursor_stats.get("portal_trips", 0) + 1
        # a jump seen from the End is the exit portal home, never the Nether
        if agent._dimension == "the End":
            where = "the Overworld"
        agent._dimension = where
        agent.memory.add_note(
            f"enter_portal: you are in {where} at ({pos['x']:.0f}, "
            f"{pos['y']:.0f}, {pos['z']:.0f}). The portal you came through stands "
            f"behind you; it takes you back the same way. Nether coordinates are the "
            f"Overworld's divided by 8.")
        LAST_FRAME.clear()               # the frame on this side is another one
        return None
    dc["t"] += 1
    if dc["t"] >= dc["n"]:
        d = math.hypot(pos["x"] - dc["x"], pos["z"] - dc["z"])
        agent._note_failure("enter_portal")
        agent.memory.add_note(
            f"enter_portal: no dimension change after {dc['t']} ticks"
            + (f", {d:.1f} blocks from the portal cell -- walk INTO the purple (go_to it "
               f"with within=0.4) and stand still." if d > 0.8 else
               " while standing in the cell -- the portal is not lit here (light_portal), "
               "or this cell is beside the purple, not in it; a portal also needs ~300 "
               "ticks after a trip before it works again."))
        return None
    # Hold the cell: a sprinting go_to overshoots its arrival by a block (a staged scene,
    # arrived, coasted 1.3 blocks out of the purple, waited outside).
    d = math.hypot(dc["x"] - pos["x"], dc["z"] - pos["z"])
    if d > 0.35:
        yaw_t = math.degrees(math.atan2(-(dc["x"] - pos["x"]), dc["z"] - pos["z"]))
        dy = MW.norm_yaw_delta(yaw_t, pos["yaw"])
        if abs(dy) > 12.0:
            return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
        return mk_act(forward=1, sneak=1, camera=[0.0, max(-6.0, min(6.0, dy))])
    return mk_act()


# -- the Nether itself: finding a fortress, a blaze, an enderman ---------------------
#
# Milestones 17-22 (kill a blaze, its rod, kill an enderman, its pearl, blaze powder,
# an eye of ender) all start with a walk nobody had ever taken: no landed run had been
# further into the Nether than the portal's obsidian platform. What the walk needs is
# public game knowledge -- fortresses are nether-brick structures, blazes live in them,
# endermen are three blocks tall and cannot hit what stands two blocks below their
# feet -- turned into closed loops on this engine's frames and statistics.

#: Ticks per block of `explore_nether` budget, plus a floor for the first tunnel.
EXPLORE_TICKS_PER_BLOCK = 9
#: Under the runner's Nether lock (agent._nether_lock: sneak on every step, no sprint,
#: no moving jump) a block takes ~15 ticks; the budget is re-based on the first tick.
EXPLORE_TICKS_PER_BLOCK_LOCKED = 18
#: Pitch held while walking: slightly down. The lava band is measured over the lower
#: 65% of the frame, which at pitch 8 is the ground from ~3 blocks out to the
#: horizon -- lava right in front is BELOW it (a staged scene: a trench 4 blocks wide
#: read 15% only once the avatar stood in it). So once any lava is in view the walk
#: tilts to EXPLORE_PITCH_LAVA, where the band covers the ground 1.5-6 blocks out and
#: an edge fills it before the feet reach it.
EXPLORE_PITCH = 8.0
EXPLORE_PITCH_LAVA = 28.0
#: Lava at this share of the lower view stops the sprint-jump (a jump carries the
#: avatar over an edge before the next frame is read) and samples every 2nd tick;
#: at EXPLORE_LAVA_BRIDGE the walk stops and a bridge is laid from where the avatar
#: stands. Sneaking does not stop a walk at an edge in this engine (measured),
#: so the edge is found by PLACING: bridge_forward's first cells fall
#: on solid floor and are refused, the first over the lava goes down (a staged scene:
#: a trench 4 blocks ahead read 4.5% at pitch 8, and the sprint-jump was in it
#: before the 5% sneak rule fired).
EXPLORE_LAVA_WALK = 0.02
EXPLORE_LAVA_BRIDGE = 0.10
#: Blocks per bridge splice, and the most splices one call makes (a probe that
#: placed nothing does not count).
BRIDGE_N, BRIDGE_MAX = 6, 8
#: Ticks of zero progress that read as a wall (tunnel) or an edge (bridge).
EXPLORE_STUCK = 6
#: Pickaxes explore_nether tunnels with, best first (netherrack breaks in a few ticks).
_PICKS = ("netherite_pickaxe", "diamond_pickaxe", "iron_pickaxe", "stone_pickaxe",
          "golden_pickaxe", "wooden_pickaxe")
_BRIDGE_BLOCKS = ("cobblestone", "netherrack", "stone", "dirt", "oak_planks",
                  "andesite", "diorite", "granite", "basalt", "blackstone")
#: The heading (yaw, 0 = +z, 90 = -x) and unit vector of each axis direction.
_AXES = {("x", 1): (-90.0, (1, 0)), ("x", -1): (90.0, (-1, 0)),
         ("z", 1): (0.0, (0, 1)), ("z", -1): (180.0, (0, -1))}


def explore_nether(cur, info: dict, axis: str = "x", sign: int = 1, length: int = 60,
                   block: str | None = None, bearing: float | None = None
                   ) -> tuple[list[dict[str, Any]], str]:
    """Walk `length` blocks along one world axis in the Nether -- or, with `bearing`,
    along that yaw -- tunnelling through netherrack and bridging lava, until a fortress
    or a blaze is in view. `bearing` is the walk TOWARD a sighting: one run (step 17727)
    was told "FORTRESS IN VIEW ... bearing yaw 61 ... travel/go_to toward
    it", turned, tunnelled 1.2 blocks with mine_forward, stalled, and went west along the
    axis instead -- the only fortress any run has seen was never approached."""
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "explore_nether: no position yet."
    if bearing is not None:
        try:
            yaw_t = (float(bearing) + 180.0) % 360.0 - 180.0
        except (TypeError, ValueError):
            return [], f"explore_nether: bearing must be a yaw in degrees, not {bearing!r}."
        ax, az = MW.facing(yaw_t)
        axis, sign = "bearing", 1
        dir_txt = f"bearing {yaw_t:.0f}"
    else:
        axis = str(axis or "x").lower()
        try:
            sign = 1 if float(sign) >= 0 else -1
        except (TypeError, ValueError):
            sign = 1
        if (axis, sign) not in _AXES:
            return [], f"explore_nether: axis must be x or z, not {axis!r}."
        yaw_t, (ax, az) = _AXES[(axis, sign)]
        dir_txt = f"{axis}{'+' if sign > 0 else '-'}"
    length = max(8, min(200, int(length)))
    pick = next((p for p in _PICKS if gui.find_slots(info, p)), None)
    acts: list[dict[str, Any]] = []
    pick_hot = None
    if pick:
        acts, err = MW._prep_item(cur, info, pick, "explore_nether")
        if err:
            return [], err
        pick_hot = MW._hotbar_of(info, pick)
    if not block:
        block = next((b for b in _BRIDGE_BLOCKS if gui.find_slots(info, b)), None)
    have_block = sum(q for _, q in gui.find_slots(info, block)) if block else 0
    budget = length * EXPLORE_TICKS_PER_BLOCK + 120
    st = {"axis": axis, "sign": sign, "yaw_t": yaw_t, "ax": ax, "az": az,
          "length": length, "budget": budget, "used": 0, "start": None, "y0": None,
          "phase": "walk", "phase_t": 0, "stuck": 0, "last": None, "broken": 0,
          "base_breaks": None, "bridges": 0, "lava": 0.0, "min_y": None,
          "pick": pick, "pick_hot": pick_hot, "block": block if have_block else None,
          "have_block": have_block, "fortress": None, "blaze": None,
          "probes": 0, "bridge_use": None, "lava_hold": 0, "dir_txt": dir_txt}
    acts.append(macros.marker("_nexplore", st, budget))
    return acts, (f"explore_nether: {length} blocks along {dir_txt} (yaw {yaw_t:.0f}), "
                  f"tunnelling with {pick or 'bare hands'}"
                  + (f", bridging with {have_block} {block}" if have_block
                     else ", NO blocks to bridge lava with")
                  + "; stops when a fortress or a blaze is in view.")


def _nexplore_finish(agent, st: dict[str, Any], why: str, flush: bool = False) -> None:
    pos = agent._cur_pos or {}
    sx, sz = st["start"] or (pos.get("x", 0.0), pos.get("z", 0.0))
    prog = (pos.get("x", 0.0) - sx) * st["ax"] + (pos.get("z", 0.0) - sz) * st["az"]
    agent.cursor_stats["explore_runs"] = agent.cursor_stats.get("explore_runs", 0) + 1
    agent.cursor_stats["explore_blocks"] = (
        agent.cursor_stats.get("explore_blocks", 0) + int(max(0.0, prog)))
    dir_txt = st.get("dir_txt") or f"{st['axis']}{'+' if st['sign'] > 0 else '-'}"
    note = (f"explore_nether({dir_txt}): walked {max(0.0, prog):.0f} of {st['length']} "
            f"blocks in {st['used']} ticks, broke {st['broken']} block(s) tunnelling"
            + (f", bridged {st['bridges']} time(s)" if st["bridges"] else "")
            + f"; now at ({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, "
              f"{pos.get('z', 0):.0f}) facing yaw {pos.get('yaw', 0):.0f}"
            + (f", lava is {100 * st['lava']:.0f}% of the lower view" if st["lava"] >= 0.02
               else "")
            + f". {why}")
    if flush:
        agent._flush_tail(note, "explore_stops")
    else:
        agent.memory.add_note(note)


@macros.tick("_nexplore", shrink="budget", moving=True)
def _nexplore_tick(agent, st: dict[str, Any], mk_act):
    from mcu_worldmodel import vision
    from mcu_worldmodel import vision_nether as VN

    if agent._gui_open:
        agent._flush_tail("explore_nether: a screen is open; movement does nothing in "
                          "the world while it is. close_inventory first.",
                          "explore_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    breaks = agent._log_breaks + agent._other_breaks
    if st["start"] is None:
        st["start"] = (pos["x"], pos["z"])
        st["y0"] = pos["y"]
        st["min_y"] = pos["y"]
        st["base_breaks"] = breaks
    st["used"] += 1
    st["min_y"] = min(st["min_y"], pos["y"])
    if (not st.get("locked") and getattr(agent, "_dimension", None) == "the Nether"
            and getattr(agent, "reflexes", True)):
        st["locked"] = True
        st["budget"] = max(st["budget"], st["length"] * EXPLORE_TICKS_PER_BLOCK_LOCKED + 120)
    prog = (pos["x"] - st["start"][0]) * st["ax"] + (pos["z"] - st["start"][1]) * st["az"]
    if prog >= st["length"]:
        _nexplore_finish(agent, st, "Done: no fortress and no blaze came into view on "
                                    "this leg. Try the other axis, or keep going.")
        return None
    if st["used"] > st["budget"]:
        _nexplore_finish(agent, st, "Budget spent.")
        return None
    if st["y0"] - pos["y"] > 4.0:
        _nexplore_finish(
            agent, st, f"STOPPED: you dropped {st['y0'] - pos['y']:.0f} blocks -- a ledge "
                       f"or a hole. Look around before walking on.", flush=True)
        return None

    # -- what the frame shows, every 6th tick (every 2nd with lava in view) ---------
    every = 2 if st["lava"] >= EXPLORE_LAVA_WALK else 6
    if st["used"] % every == 0 and agent._last_pov is not None:
        frame = np.asarray(agent._last_pov)
        fv = VN.fortress_in_view(frame)
        if fv is not None:
            frac, off = fv
            bearing = (pos["yaw"] + off + 180.0) % 360.0 - 180.0
            st["fortress"] = (frac, bearing)
            agent.cursor_stats["fortress_seen"] = (
                agent.cursor_stats.get("fortress_seen", 0) + 1)
            data = agent._encode_pov(agent._last_pov, agent.step)
            rel = agent.memory.save_frame(agent.step, data, suffix="_fortress") if data else None
            _nexplore_finish(
                agent, st,
                f"FORTRESS IN VIEW: nether bricks (dark red-brown) fill {100 * frac:.0f}% "
                f"of the view, centred {off:+.0f} degrees from your heading -- bearing "
                f"yaw {bearing:.0f}. Blazes live in a fortress's corridors and spawners "
                f"(and it stands on nether brick, never on netherrack): "
                f"explore_nether(bearing={bearing:.0f}, length=40) walks TOWARD it with "
                f"the same tunnelling and bridging (call it again while the bricks grow "
                f"in the view; 1% is a sighting, not an arrival), and fight_blaze() when "
                f"one is in view."
                + (f" The frame is saved at {rel} and attached to your next turn." if rel
                   else ""), flush=True)
            return None
        bh = VN.blaze_hint(frame)
        if bh is not None:
            st["blaze"] = bh
            agent.cursor_stats["blaze_seen"] = agent.cursor_stats.get("blaze_seen", 0) + 1
            off = (bh[1] - frame.shape[1] / 2.0) * VN.DEG_PER_PX
            _nexplore_finish(
                agent, st,
                f"A BLAZE is in view ({bh[3]} px at screen ({bh[1]}, {bh[2]}), "
                f"{off:+.0f} degrees from your heading). It shoots fire from range: "
                f"fight_blaze() now, with a sword out.", flush=True)
            return None
        if st["used"] >= int(st.get("lava_hold", 0)):
            st["lava"] = vision.lava_fraction(frame)

    # -- heading first: a large yaw error is corrected standing still ----------------
    dy = MW.norm_yaw_delta(st["yaw_t"], pos["yaw"])
    if abs(dy) > 10.0:
        st["stuck"] = 0
        return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])

    ph = st["phase"]
    if ph == "walk":
        low = (st["lava"] >= EXPLORE_LAVA_WALK
               or st["used"] < int(st.get("lava_hold", 0)))
        dp = (EXPLORE_PITCH_LAVA if low else EXPLORE_PITCH) - pos["pitch"]
        last = st.get("last")
        moved = math.hypot(pos["x"] - last[0], pos["z"] - last[1]) if last else None
        st["last"] = (pos["x"], pos["z"])
        if moved is not None and moved < 0.03:
            st["stuck"] += 1
        else:
            st["stuck"] = 0
        careful = (st["lava"] >= EXPLORE_LAVA_WALK
                   or st["used"] < int(st.get("lava_hold", 0)))
        if st["lava"] >= EXPLORE_LAVA_BRIDGE and not st["block"]:
            # no block to bridge with: stop before the pool instead of walking into it
            # (audit pass 14: the stuck path never fires on open lava, and the runner's
            # lava guard is off above y 40, i.e. for most of the Nether)
            _nexplore_finish(agent, st, f"lava fills {100 * st['lava']:.0f}% of the lower "
                             f"view and you carry no block to bridge with -- stopped before "
                             f"the pool; bring 16+ cobblestone, or explore the other axis",
                             flush=True)
            return None
        if st["lava"] >= EXPLORE_LAVA_BRIDGE and st["block"]:
            # Only from the ground: a bridge compiled mid-jump takes the airborne y
            # as its floor and stops at once as "dropped below the bridge level"
            # (a staged scene: compiled at y 72 over a floor at 71).
            grounded = (abs(pos["y"] - round(pos["y"])) < 0.05
                        and st.get("last_y") is not None
                        and abs(pos["y"] - st["last_y"]) < 0.01)
            st["last_y"] = pos["y"]
            if grounded:
                return _nexplore_bridge(agent, st, mk_act)
            return mk_act()
        st["last_y"] = pos["y"]
        if st["stuck"] >= EXPLORE_STUCK:
            st["stuck"] = 0
            if careful:
                return _nexplore_bridge(agent, st, mk_act)
            st["phase"], st["phase_t"], st["base_breaks"] = "foot", 0, breaks
            return mk_act()
        return mk_act(forward=1, sprint=0 if careful else 1, jump=0 if careful else 1,
                      camera=[max(-6.0, min(6.0, dp)), max(-6.0, min(6.0, dy))])

    # -- tunnelling: the foot block, then the eye block, then walk again -- the same
    # cut and the same pitches as the runner's displacement-verified mining cycle
    # (agent._mfwd_tick: 35 then 8), which has the tick evidence behind it.
    target = 35.0 if ph == "foot" else 8.0
    dp = target - pos["pitch"]
    st["phase_t"] += 1
    if abs(dp) > 4.0 and st["phase_t"] <= 12:
        return mk_act(camera=[max(-20.0, min(20.0, dp)), 0.0])
    if breaks > st["base_breaks"] + 0.5:
        st["broken"] += 1
        st["base_breaks"] = breaks
        st["phase"], st["phase_t"] = ("eye" if ph == "foot" else "walk"), 0
        return mk_act()
    if st["phase_t"] > 34:
        st["phase"], st["phase_t"] = ("eye" if ph == "foot" else "walk"), 0
        return mk_act()
    return mk_act(attack=1)


def _nexplore_bridge(agent, st: dict[str, Any], mk_act):
    """An edge reached with lava in view: splice a sneaking bridge_forward behind this
    marker, then a continuation of the same walk, and let the queue run them."""
    from mcu_worldmodel import procedures as P

    # A splice that laid no block was a probe of solid floor (its cells were refused);
    # only real bridges count toward the cap, and a probe that gained no ground twice
    # in a row means the lava is beside the path, not across it: walk on.
    placed_now = agent.stat_now("use_item", st["block"]) if st["block"] else 0.0
    if st.get("bridge_use") is not None:
        if placed_now > st["bridge_use"]:
            st["bridges"] += 1
            st["probes"] = 0
        else:
            st["probes"] = int(st.get("probes", 0)) + 1
    if st["bridges"] >= BRIDGE_MAX:
        _nexplore_finish(agent, st, f"STOPPED at an edge over lava after {BRIDGE_MAX} "
                                    f"bridges ({BRIDGE_MAX * BRIDGE_N} blocks): this lake "
                                    f"is wide. Turn: try the other axis from here.",
                         flush=True)
        return None
    if not st["block"]:
        _nexplore_finish(agent, st, "STOPPED at an edge over lava with no blocks to "
                                    "bridge with (carry cobblestone or netherrack). "
                                    "Turn: try the other axis from here.", flush=True)
        return None
    if int(st.get("probes", 0)) >= 3:
        # Three probes in a row placed nothing: the lava in view is not on the path.
        st["probes"], st["lava"], st["bridge_use"] = 0, 0.0, None
        st["lava_hold"] = st["used"] + 20      # walk on (no jump), sample again after
        return mk_act(forward=1)
    info = agent._cur_info or {}
    acts, note = MW.bridge_forward(agent.cursor.copy(), info, n=BRIDGE_N, item=st["block"])
    if not acts:
        _nexplore_finish(agent, st, f"STOPPED at an edge over lava; the bridge could not "
                                    f"be compiled: {note}", flush=True)
        return None
    if st["pick_hot"] is not None:
        acts += P.equip_hotbar(int(st["pick_hot"]) + 1)
    cont = dict(st)
    # The lava reading is KEPT: the continuation must start careful (no jump, a 2-tick
    # sample) -- reset to 0 it sprint-jumped off the edge the failed bridge had found
    # (run 5). The next sample overwrites it within two ticks anyway.
    cont.update({"phase": "walk", "phase_t": 0, "stuck": 0, "last": None,
                 "last_y": None, "bridge_use": placed_now})
    rest = max(60, st["budget"] - st["used"])
    acts.append(macros.marker("_nexplore", cont, rest))
    idx = agent.queue[0][1] if agent.queue else 0
    for step in reversed(acts):
        agent.queue.insert(1, (step, idx))
    agent.cursor_stats["explore_bridges"] = agent.cursor_stats.get("explore_bridges", 0) + 1
    pos = agent._cur_pos or {}
    agent.memory.add_note(
        f"explore_nether: lava ahead ({100 * st['lava']:.0f}% of the lower view) at "
        f"({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, {pos.get('z', 0):.0f}) -- laying "
        f"{BRIDGE_N} {st['block']} ahead at foot level (cells still solid are refused, "
        f"the first over the lava goes down), then walking on.")
    return None


def fight_blaze(cur, info: dict, ticks: int = 300, retreat_hp: float = 6.0,
                weapon: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """`fight` with the blaze detector (its yellow is lava's; the rods are the tell)."""
    from mcu_worldmodel import macros_entity as ME

    acts, note = ME.fight(cur, info, ticks=ticks, retreat_hp=retreat_hp, weapon=weapon,
                          label="blaze", detect="blaze")
    if not acts:
        return [], note
    return acts, (note + " A blaze hovers 1-3 blocks up and shoots fire from range: the "
                         "loop walks in under it when swings miss; break its line of "
                         "sight (a wall, a corner) when your health falls.")


def enderman_pit(cur, info: dict) -> tuple[list[dict[str, Any]], str]:
    """A 2-deep, 1x1 pit under the feet: an enderman (2.9 blocks tall, melee reach
    ~1.4 blocks from its feet) standing at the rim is 2 blocks above you and cannot
    hit you, while your sword (reach 3) reaches its legs. Then fight(label="enderman")."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "enderman_pit: no position yet."
    pick = next((p for p in _PICKS if gui.find_slots(info, p)), None)
    acts: list[dict[str, Any]] = []
    if pick:
        acts, err = MW._prep_item(cur, info, pick, "enderman_pit")
        if err:
            return [], err
    acts += P.dig_down(n=160, until_y=pos["y"] - 2.0)
    acts += P.look_abs(pitch=-50.0, ticks=20)
    acts.append(macros.marker("_pitcheck", {"t": 0, "y0": float(pos["y"])}, 4))
    return acts, (f"enderman_pit: digging 2 blocks straight down from y {pos['y']:.0f} "
                  f"with {pick or 'bare hands'}, then looking up at the rim")


@macros.tick("_pitcheck")
def _pitcheck_tick(agent, pc: dict[str, Any], mk_act):
    if pc["t"] < 3:
        pc["t"] += 1
        return mk_act()
    pos = agent._cur_pos or {}
    depth = pc["y0"] - float(pos.get("y", pc["y0"]))
    if depth >= 1.9:
        agent.cursor_stats["enderman_pits"] = agent.cursor_stats.get("enderman_pits", 0) + 1
        agent.memory.add_note(
            f"enderman_pit: you stand in a {depth:.0f}-deep pit at ({pos.get('x', 0):.0f}, "
            f"{pos.get('y', 0):.0f}, {pos.get('z', 0):.0f}). An enderman at the rim cannot "
            f"reach you here; look at it to make it come (endermen attack whoever meets "
            f"their eyes), then fight(label=\"enderman\") from the pit -- its legs are at "
            f"the rim. After the kill, pillar_up(2) and collect_drops for the pearl "
            f"(about one kill in two drops one).")
        return None
    agent._note_failure("enderman_pit")
    agent.memory.add_note(
        f"enderman_pit: only {depth:.1f} blocks down -- the pit is not deep enough to be "
        f"safe (2 needed). The block under you may be unbreakable with this tool or the "
        f"dig stalled; step one block over and call it again.")
    return None


def _install_detectors() -> None:
    from mcu_worldmodel import macros_entity as ME
    from mcu_worldmodel import vision_nether as VN

    ME.DETECTORS["blaze"] = VN.blaze_hint
    ME.DETECTORS["enderman"] = VN.enderman_hint


_install_detectors()


# -- registration -------------------------------------------------------------------

def register_all(register, Procedure) -> None:
    register(Procedure(
        "explore_nether",
        "Walk `length` blocks along one world axis IN THE NETHER looking for a fortress: "
        "keeps the heading, tunnels through netherrack when a wall stops you (eye block, "
        "foot block, walk), sneaks when lava fills the lower view and bridges an edge "
        "with your blocks, and STOPS the moment a nether-brick mass (a fortress) or a "
        "blaze is in view, saying the bearing. Reports blocks walked, tunnelled, bridged "
        "and where you are. Fortresses run along the x or z axis in long lines, so one "
        "leg per axis finds one where nothing else would; with `bearing` it walks along "
        "that yaw instead (toward a sighting).",
        explore_nether, needs_cursor=True, needs_info=True,
        preconditions="In the Nether, no screen open, a pickaxe carried (netherrack is "
                      "soft) and 8+ cobblestone/netherrack for bridging lava.",
        params={"axis": "x or z", "sign": "+1 or -1 (the direction along it)",
                "bearing": "a yaw in degrees to walk along instead of an axis (toward a sighting; optional)",
                "length": "blocks to cover, 8-200 (default 60; ~9 ticks per block)",
                "block": "block to bridge with (default: cobblestone, then netherrack)"}))
    register(Procedure(
        "fight_blaze",
        "Melee a BLAZE to death with the blaze detector (in the Nether the plain fight "
        "mistakes lava for its yellow): faces it, walks in under it when swings miss, "
        "pulses attack, verifies kill_entity.blaze; then collect_drops for the rod.",
        fight_blaze, needs_cursor=True, needs_info=True,
        preconditions="A blaze in view (explore_nether's note, or scan_around), a sword "
                      "carried, health above 10 -- it shoots fire from range.",
        params={"ticks": "budget, 40-400 (default 300)",
                "retreat_hp": "back off at this health (default 6)",
                "weapon": "item to fight with (default: your best sword)"}))
    register(Procedure(
        "enderman_pit",
        "Dig a 2-deep, 1x1 pit under your feet and look up at the rim: an enderman is "
        "three blocks tall and cannot hit what stands two blocks below its feet, while "
        "your sword reaches its legs. Then fight(label=\"enderman\") from inside; after "
        "the kill, pillar_up(2) and collect_drops for the pearl.",
        enderman_pit, needs_cursor=True, needs_info=True,
        preconditions="Solid ground (not over lava), a pickaxe carried, an enderman "
                      "near (they wander the Nether's warped forests and the "
                      "Overworld at night) but NOT yet angry -- look at it only from "
                      "the pit.",
        params={}))
    register(Procedure(
        "find_lava",
        "Find the lava the obsidian needs. Takes a staircase down to about y 11 if you "
        "are above it, then tunnels in straight legs (turning 90 degrees after each), "
        "watching the lower view for lava the whole way. STOPS the moment lava comes "
        "into view, at least 2 blocks short of it, and the note names the pool's cell, "
        "the RIM cell to pour from and the exact `make_obsidian(x, y, z)` call -- so a "
        "sighting turns into obsidian in one more step. Says how many blocks it searched "
        "and where to go next when it finds nothing.",
        find_lava, needs_cursor=True, needs_info=True,
        preconditions="Underground (it is meant for y <= 15), a pickaxe carried, no "
                      "screen open; carry the water_bucket so the pour can follow at "
                      "once (fetch_water/fill_bucket first if you do not).",
        params={"n": "tick budget, 250-1500 (default 600, about 27 blocks of tunnel)",
                "y": "level to search at (default 11)",
                "leg": "blocks per straight leg before the 90-degree turn (default 40)"}))
    register(Procedure(
        "make_obsidian",
        "Turn lava into obsidian: pours a water bucket onto the TOP of the block at (x, y, "
        "z) -- a solid block at the edge of a lava pool -- waits for the flow to quench the "
        "lava sources, and scoops the water back (walking back into reach if the flow "
        "pushed you). With no x, y, z it pours on the last sighting's rim (find_lava's "
        "stop, or a LAVA AHEAD note with the bucket carried). Then mine_obsidian().",
        make_obsidian, needs_cursor=True, needs_info=True,
        preconditions="Carry a water_bucket; stand 2-3 blocks from the pool on its rim, "
                      "the rim block within 4 blocks. Flowing lava turns to cobblestone, "
                      "only SOURCE blocks (still lava) become obsidian.",
        params={"x": "rim block x (optional: with no x, y, z the last sighting's rim is used)",
                "y": "rim block y", "z": "rim block z"}))
    register(Procedure(
        "mine_obsidian",
        "Break the obsidian block at (x, y, z) with the diamond pickaxe: the aim is held on "
        "the block's centre every tick and the attack never released (about 190 ticks), "
        "stops the moment `mine_block obsidian` moves, then sweeps the drop. With no x, y, "
        "z it mines the last sighting's pool cell. Put it FIRST in its plan: it needs "
        "240 ticks and is dropped whole when fewer are left.",
        mine_obsidian, needs_cursor=True, needs_info=True,
        preconditions="A diamond pickaxe carried; the block within 4 blocks.",
        params={"x": "block x (optional: with no x, y, z the last sighting's pool cell)",
                "y": "block y", "z": "block z",
                "ticks": "budget, 240-400 (default 300)"}))
    register(Procedure(
        "build_portal_frame",
        "Place the 14-obsidian outline of a nether portal (4 wide x 5 high, corners "
        "included) standing on the ground `dist` blocks ahead of you, across your "
        "facing; every block verified; call again to fill what was refused.",
        build_portal_frame, needs_cursor=True, needs_info=True,
        preconditions="14 obsidian (10 is the minimum frame; this places the corners "
                      "too so each block has a neighbour to build on); flat ground "
                      "ahead; stand 2 blocks back from the line, facing it.",
        params={"item": "obsidian", "dist": "blocks ahead (2-3)"}))
    register(Procedure(
        "light_portal",
        "Light the frame built by build_portal_frame from the same spot: flint_and_steel "
        "on the inside of its bottom row; checks the purple appears.",
        light_portal, needs_cursor=True, needs_info=True,
        preconditions="Same position and facing as build_portal_frame; flint_and_steel "
                      "carried.",
        params={"dist": "the dist the frame was built with"}))
    register(Procedure(
        "enter_portal",
        "Walk into the lit portal (the frame built from this spot, or the cell at x, z) "
        "and stand until the dimension changes; reports where you arrived.",
        enter_portal, needs_cursor=True, needs_info=True,
        preconditions="The portal is lit (light_portal's note). Takes ~4 s in the "
                      "purple; the trip back is the same call from the other side.",
        params={"dist": "the dist the frame was built with",
                "x": "portal cell x (optional)", "z": "portal cell z (optional)"}))
