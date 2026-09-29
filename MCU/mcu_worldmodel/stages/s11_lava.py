"""Stage 11: finding lava at depth and turning the sighting into obsidian.

Two things are measured here, both on the real camera and the real blocks:

1. The geometry. A 3x3 lava pool sits at a KNOWN offset in a lit stone room at y 11, and
   `vision.lava_view` + `macros_nether.lava_cells` have to say where it is from one
   frame, from three poses: straight ahead, 30 degrees off the heading, and with the pool
   sunk one block below the feet. The camera's field of view (70 vertical / ~102
   horizontal at 16:9) is fitted from the same frames rather than assumed.
2. The macro. `find_lava` is run from 8+ blocks away in a 1-wide tunnel: it has to walk,
   stop SHORT of the pool, and name a rim cell within 1.5 blocks of the true rim -- and
   the `make_obsidian` call it names, run verbatim, has to produce obsidian that
   `mine_obsidian` then breaks.

Run from the repo root:
    source ./env.sh
    MCU_STAGE_OUT=logs/stages xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s11_lava
"""
from __future__ import annotations

import math
import re

import numpy as np

from mcu_worldmodel import macros_nether as MN
from mcu_worldmodel import macros_world as MW
from mcu_worldmodel import vision
from mcu_worldmodel.stages.rig import SPAWN, P, Rig, main_guard

#: The room's floor: the avatar's feet at Y, the floor blocks (and a flush pool) at Y-1.
Y = 11
#: The pool's near edge, in blocks north (+z) of the room's origin.
POOL_DZ = 14


def _read(rig: Rig, pitch: float) -> tuple[float, float, float, float]:
    """`vision.lava_view` measured the way find_lava measures it: from one degree below
    the horizon, so a tilted view keeps the ground in the band."""
    rows_from = min(0.55, max(0.10, 0.5 - float(pitch) / MN.LAVA_VFOV + 0.012))
    return vision.lava_view(np.asarray(rig.info["pov"]), rows_from=rows_from)


def _room(rig: Rig, bx: int, bz: int) -> None:
    """A lit stone room 9 wide, 2 high, 30 long at y 11, solid rock all round it."""
    rig.fill(bx - 8, Y - 8, bz - 6, bx + 8, Y + 8, bz + 34, "stone")
    rig.fill(bx - 4, Y, bz - 4, bx + 4, Y + 1, bz + 30, "air")
    for zz in range(bz - 4, bz + 30, 3):            # glowstone in the ceiling
        rig.fill(bx - 3, Y + 2, zz, bx + 3, Y + 2, zz, "glowstone")


def stage(rig: Rig) -> None:
    x, _, z = SPAWN
    bx, bz = math.floor(x), math.floor(z)
    pz = bz + POOL_DZ
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/weather clear")
    _room(rig, bx, bz)
    # The pool: 3x3 of lava SOURCES flush with the floor. Its neighbours at that level
    # are stone, so nothing flows and the sources stay sources.
    rig.fill(bx - 1, Y - 1, pz, bx + 1, Y - 1, pz + 2, "lava")
    rig.tp(bx + 0.5, Y, bz + 0.5, yaw=0, pitch=8)
    rig.clear()
    rig.idle(20)
    rig.frame("s11_room")

    # -- 1. the geometry, from three poses --------------------------------------------
    true_rim = (bx, Y - 1, pz - 1)
    fits: list[float] = []

    def pose(label: str, dz: int, yaw: float, pitch: float, drop: int = 0,
             hidden: bool = False) -> dict:
        """Stand `dz` cells short of the pool's near edge and read one frame."""
        az = pz - dz
        rig.tp(bx + 0.5, Y, az + 0.5, yaw=yaw, pitch=pitch)
        rig.idle(12)
        p = rig.pos() or {}
        frac, cx, bottom, top = _read(rig, float(p.get("pitch", pitch)))
        cells = MN.lava_cells(p, cx, bottom, top=top,
                              min_dist=MN.FIND_MIN_DIST) if frac else None
        L = pz - (az + 0.5)                          # true distance to the near edge
        rig.frame(f"s11_pose_{label}")
        if hidden:
            # A pool `drop` below the floor is hidden behind its own lip beyond
            # W * EYE / drop blocks: the ray that grazes the lip lands past the pool's
            # far edge. This pose is that limit, asserted rather than assumed.
            rig.log(f"pose {label}: true L {L:.1f} drop {drop} | frac {frac:.4f} "
                    f"(the lip hides everything past {L * (1 + drop / MW.EYE):.1f} "
                    f"blocks, the pool ends at {L + 3:.1f})")
            rig.check(f"pose {label}: a pool one block down is INVISIBLE at {L:.1f} "
                      f"blocks -- its own lip hides it (measured, not assumed)",
                      frac < MN.FIND_SEEN, (frac, cx, bottom))
            return {}
        if cells is None:
            rig.log(f"pose {label}: NO lava read (frac {frac:.4f}) at {p}")
            rig.check(f"pose {label}: the pool is in view and placed", False,
                      (frac, cx, bottom, p))
            return {}
        err = abs(cells["dist"] - L)
        rerr = math.dist(cells["rim"], true_rim)
        # The field of view, fitted from this frame instead of assumed: the horizontal
        # half-angle that would put the mass's centroid on its true bearing.
        true_bear = math.degrees(math.atan2(-(bx + 0.5 - (bx + 0.5)), L))
        rel = MW.norm_yaw_delta(true_bear, float(p.get("yaw", yaw)))
        if abs(cx) > 0.02:
            fits.append(2.0 * math.degrees(math.atan(math.tan(math.radians(rel))
                                                     / (2.0 * cx))))
        rig.log(f"pose {label}: true L {L:.1f} drop {drop} | frac {frac:.3f} cx {cx:+.3f} "
                f"bottom {bottom:.3f} -> dist {cells['dist']:.2f} (err {err:.2f}), "
                f"bearing {cells['bearing']:.1f} (rel {rel:+.1f}), drop {cells['drop']}, "
                f"pool {cells['pool']}, rim {cells['rim']} (err {rerr:.2f})")
        rig.check(f"pose {label}: the pool's near edge is placed within 1.5 blocks "
                  f"(err {err:.2f})", err <= 1.5, (L, cells))
        rig.check(f"pose {label}: the named rim is within 1.5 blocks of the true rim "
                  f"(err {rerr:.2f})", rerr <= 1.5, (true_rim, cells["rim"]))
        return cells

    pose("ahead", 8, 0.0, 12.0)
    pose("off30", 8, -30.0, 12.0)

    # The same pool sunk one block: its lip now occludes the lava's near edge, and the
    # reading should still land on the lip -- which is where the rim block is.
    rig.fill(bx - 1, Y - 1, pz, bx + 1, Y - 1, pz + 2, "air")
    rig.fill(bx - 1, Y - 2, pz, bx + 1, Y - 2, pz + 2, "lava")
    rig.idle(10)
    pose("below_far", 7, 0.0, 15.0, drop=1, hidden=True)
    pose("below", 3, 0.0, 20.0, drop=1)
    rig.fill(bx - 1, Y - 2, pz, bx + 1, Y - 2, pz + 2, "stone")
    rig.fill(bx - 1, Y - 1, pz, bx + 1, Y - 1, pz + 2, "lava")
    rig.idle(10)

    if fits:
        rig.log(f"fitted horizontal field of view: {sum(fits) / len(fits):.1f} degrees "
                f"(the constant is {MN.LAVA_HFOV:.1f})")
        rig.check(f"the horizontal field of view fits {sum(fits) / len(fits):.0f} degrees, "
                  f"within 8 of the {MN.LAVA_HFOV:.0f} the geometry assumes",
                  abs(sum(fits) / len(fits) - MN.LAVA_HFOV) <= 8.0, fits)

    # -- 2. find_lava down a 1-wide tunnel --------------------------------------------
    # Fill the room back in and leave a 1-wide, 2-high corridor to the pool, so the walk
    # has walls the way a real strip mine does.
    rig.fill(bx - 4, Y, bz - 4, bx + 4, Y + 1, pz - 1, "stone")
    rig.fill(bx, Y, bz - 2, bx, Y + 1, pz - 1, "air")
    rig.fill(bx - 1, Y, pz - 1, bx + 1, Y + 1, pz + 3, "air")
    for zz in range(bz - 2, pz, 4):
        rig.setblock(bx, Y + 2, zz, "glowstone")
    start_z = pz - 10
    rig.tp(bx + 0.5, Y, start_z + 0.5, yaw=0, pitch=8)
    rig.give("diamond_pickaxe", 1)
    rig.give("water_bucket", 1)
    rig.give("cobblestone", 16)
    rig.idle(12)
    rig.frame("s11_tunnel")
    r = rig.run([P("find_lava", n=420)], label="find_lava", max_ticks=520)
    p = rig.pos() or {}
    note = " ".join(r["notes"])
    m = re.search(r"make_obsidian\((-?\d+), (-?\d+), (-?\d+)\)", note)
    rim = tuple(int(g) for g in m.groups()) if m else None
    rerr = math.dist(rim, true_rim) if rim else 99.0
    rig.log(f"find_lava stopped at {p}; rim named {rim}, true {true_rim}, err {rerr:.2f}")
    rig.frame("s11_found")
    rig.check("find_lava: the lava was found and the walk stopped short of the pool",
              any("LAVA FOUND" in n for n in r["notes"])
              and p.get("z", 99.0) <= pz - 2.0, (p, r["notes"]))
    rig.check(f"find_lava: the named rim is within 1.5 blocks of the true rim "
              f"(err {rerr:.2f})", rerr <= 1.5, (rim, true_rim, note[-400:]))
    rig.check("find_lava: the note names the make_obsidian call and keeps the warning",
              rim is not None and "Do NOT walk any closer" in note, note[-300:])

    # -- 3. the call the note named, run verbatim -------------------------------------
    if rim is None:
        rim = true_rim
    s0 = rig.stats()
    r = rig.run([P("make_obsidian", x=rim[0], y=rim[1], z=rim[2])],
                label=f"make_obsidian{rim}", max_ticks=400)
    rig.frame("s11_poured")
    rig.check("make_obsidian on the named rim: the water went out and came back",
              r["inv"].get("water_bucket", 0) == 1
              and any("obsidian now" in n for n in r["notes"]), (r["inv"], r["notes"]))
    # The pool cells are the three at (bx-1..bx+1, Y-1, pz); the nearest is the one the
    # water reached first.
    got = False
    for tx in (bx, bx - 1, bx + 1):
        s1 = rig.stats()
        r = rig.run([P("mine_obsidian", x=tx, y=Y - 1, z=pz)],
                    label=f"mine_obsidian ({tx}, {Y - 1}, {pz})", max_ticks=500)
        d = rig.stat_delta(s1, rig.stats())
        if d.get("mine_block.obsidian", 0) >= 1 or r["inv"].get("obsidian", 0) >= 1:
            got = True
            break
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s11_mined")
    rig.check("the poured rim really made obsidian: a block of it broke",
              got or d.get("mine_block.obsidian", 0) >= 1, (d, rig.inv()))


if __name__ == "__main__":
    main_guard(stage)
