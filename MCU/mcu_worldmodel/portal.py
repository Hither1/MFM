"""Ground truth for a nether portal: which cell each obsidian block actually went in.

Why this module exists. A nether portal is the one goal in the dragon chain that no
text state can settle. `inventory` says ten obsidian left the hotbar; `use_item` says
ten placements happened; `mine_block` says how many came back. None of them says
*where*, and where is the entire task -- a 4x5 vertical outline whose four corners may
be omitted (so ten blocks is exactly enough) and whose 2x3 interior must be air. Get
one cell wrong and the flint and steel lights a fire instead of a portal, and every
statistic the agent can read still reads "ten placed, one lit".

Measured on early runs of this task: agents handed the blocks struck the flint and
steel into frames that were 4, 5, 6 and 6 cells right out of ten -- and then struck again at the *identical* geometry, five and seven times over,
because nothing they could read told them which cell was wrong. That is the case this
module measures, and it is why the readout here is a *cell list*, not a count.

Supply is deliberately not part of it. The task hands out a full stack, so an agent can
never be stuck for want of a block; every failure is a failure to put blocks in the
right cells and to notice that they are not.

What the engine gives us. `action["voxels"] = [x0, x1, y0, y1, z0, z1]` makes the
client answer with one JSON object per NON-AIR block in that box (`EnvServer`, decompiled):

    for x in range(x0, x1):          # half-open, all three axes
      for y in range(y0, y1):
        for z in range(z0, z1):
          if not world.getBlockState(BlockPos(player).add(x, y, z)).isAir():
              emit {"x": x, "y": y, "z": z, "type": "minecraft:obsidian"}

Three consequences the code below depends on:

  * the coordinates are OFFSETS from the player's block position, not absolutes, so a
    trace has to add `floor(player x/y/z)` back before anything can be accumulated
    across steps -- the agent walks while it builds;
  * air is *absent*, never reported, so "this interior cell is clear" is proved by a
    cell being inside the queried box and missing from the answer, and cannot be
    proved at all for a cell the box did not cover;
  * the bounds are exclusive at the top, so a window of (-8, 9) spans -8..8.

Nothing here is ever shown to the agent. The whole point of the probe is that the
geometry is checkable only by looking, so an environment that hands back
"your left column is one block short" would answer the question it is meant to ask.
The report is written for the scorer; see `portal_probe.PortalProbeCallback` for the
one place that reads a live `info` and the allowlist in `src/agent.py` that keeps
`voxels` out of the observation the agent receives.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

Cell = tuple[int, int, int]

OBSIDIAN = "minecraft:obsidian"
PORTAL = "minecraft:nether_portal"
FIRE = "minecraft:fire"

#: Blocks that do not stop a portal forming. Air is not here because air is never
#: reported; a cell is passable by being absent. Fire is what the flint and steel
#: leaves in the interior, and the portal blocks are what replaces it.
PASSABLE = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air",
                      FIRE, PORTAL})

#: The interior of the smallest legal portal: 2 wide, 3 tall.
INTERIOR_W, INTERIOR_H = 2, 3

#: How the frame plane is oriented. "x" varies along x at a fixed z; "z" varies along
#: z at a fixed x. A portal is always vertical, so y is never the free axis.
AXES = ("x", "z")


def _unit(axis: str) -> Cell:
    return (1, 0, 0) if axis == "x" else (0, 0, 1)


def _add(c: Cell, d: Cell, k: int = 1) -> Cell:
    return (c[0] + d[0] * k, c[1] + d[1] * k, c[2] + d[2] * k)


@dataclass(frozen=True)
class FrameCells:
    """The cells of one candidate portal, keyed off the interior's bottom-left corner.

    `required` is the ten blocks a portal genuinely needs -- two under the interior,
    two over it, and three up each side. `corners` is the four a builder usually wants
    anyway, because with ten obsidian and nothing else there is no neighbouring block
    to place the top row against; the task config hands out cobblestone for exactly
    that reason. A corner made of cobblestone is correct, so `required` is the test and
    `corners` is only reported.
    """

    anchor: Cell
    axis: str
    required: tuple[Cell, ...]
    corners: tuple[Cell, ...]
    interior: tuple[Cell, ...]


def frame_cells(anchor: Cell, axis: str) -> FrameCells:
    """The cells of the portal whose interior bottom-left cell is `anchor`."""
    u = _unit(axis)
    up = (0, 1, 0)
    interior = tuple(_add(_add(anchor, u, i), up, j)
                     for j in range(INTERIOR_H) for i in range(INTERIOR_W))
    bottom = tuple(_add(_add(anchor, u, i), up, -1) for i in range(INTERIOR_W))
    top = tuple(_add(_add(anchor, u, i), up, INTERIOR_H) for i in range(INTERIOR_W))
    left = tuple(_add(_add(anchor, u, -1), up, j) for j in range(INTERIOR_H))
    right = tuple(_add(_add(anchor, u, INTERIOR_W), up, j) for j in range(INTERIOR_H))
    corners = (_add(_add(anchor, u, -1), up, -1),
               _add(_add(anchor, u, INTERIOR_W), up, -1),
               _add(_add(anchor, u, -1), up, INTERIOR_H),
               _add(_add(anchor, u, INTERIOR_W), up, INTERIOR_H))
    return FrameCells(anchor=anchor, axis=axis,
                      required=bottom + top + left + right,
                      corners=corners, interior=interior)


#: Where each required cell sits relative to the anchor, per axis. Candidate frames are
#: generated by subtracting these from every obsidian block that has been seen: any
#: real frame has each of its ten blocks in one of these ten roles.
def _required_offsets(axis: str) -> tuple[Cell, ...]:
    return frame_cells((0, 0, 0), axis).required


@dataclass
class FrameFit:
    """How close one candidate frame is to being a portal, and in what way it is not."""

    anchor: Cell
    axis: str
    matched: tuple[Cell, ...] = ()          # required cells that hold obsidian
    missing: tuple[Cell, ...] = ()          # required cells that do not
    wrong_block: tuple[Cell, ...] = ()      # required cells holding something else
    blocked: tuple[Cell, ...] = ()          # interior cells holding a solid block
    unknown: tuple[Cell, ...] = ()          # cells never covered by a voxel query
    corners_present: int = 0
    lit_cells: int = 0                      # interior cells that are nether_portal

    @property
    def n_matched(self) -> int:
        return len(self.matched)

    @property
    def complete(self) -> bool:
        """Every required cell is obsidian and the interior is clear and known."""
        return (len(self.missing) == 0 and len(self.blocked) == 0
                and len(self.unknown) == 0)

    @property
    def lit(self) -> bool:
        return self.lit_cells >= INTERIOR_W * INTERIOR_H

    def rank(self) -> tuple:
        """Sort key for picking the frame the builder was evidently aiming at."""
        return (len(self.matched), -len(self.blocked), -len(self.unknown),
                self.corners_present, self.lit_cells)

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchor": list(self.anchor), "axis": self.axis,
            "matched": len(self.matched), "of": len(_required_offsets(self.axis)),
            "missing": [list(c) for c in self.missing],
            "wrong_block": [list(c) for c in self.wrong_block],
            "blocked_interior": [list(c) for c in self.blocked],
            "unknown": [list(c) for c in self.unknown],
            "corners_present": self.corners_present,
            "lit_cells": self.lit_cells,
            "complete": self.complete, "lit": self.lit,
        }


class World:
    """What the voxel queries have proved about the blocks, accumulated over a run.

    Two maps, because "not obsidian" and "not seen" are different answers and the
    difference is the whole reliability of the readout. `solid` holds every non-air
    block ever reported, keyed by absolute cell; `seen` holds every cell any query has
    covered, whether or not something was in it. A cell in `seen` and not in `solid` is
    air, proved. A cell in neither is unknown, and a frame with unknown cells is never
    scored complete.
    """

    def __init__(self) -> None:
        self.solid: dict[Cell, str] = {}
        self.seen: set[Cell] = set()

    def apply(self, origin: Cell, window: Iterable[int], blocks: dict[Cell, str]
              ) -> tuple[list[tuple[Cell, str]], list[tuple[Cell, str]]]:
        """Fold one query in. Returns (appeared, vanished) as absolute cells.

        `appeared` is every cell that now holds a block and did not before -- the
        ground-truth placement history, the thing an agent's own notes leave out.
        `vanished` is every cell whose block is gone, i.e. mined.
        """
        x0, x1, y0, y1, z0, z1 = list(window)
        appeared: list[tuple[Cell, str]] = []
        vanished: list[tuple[Cell, str]] = []
        for dx in range(x0, x1):
            for dy in range(y0, y1):
                for dz in range(z0, z1):
                    cell = (origin[0] + dx, origin[1] + dy, origin[2] + dz)
                    was = self.solid.get(cell)
                    now = blocks.get(cell)
                    if now is not None and now != was:
                        appeared.append((cell, now))
                        self.solid[cell] = now
                    elif now is None and was is not None:
                        vanished.append((cell, was))
                        del self.solid[cell]
                    self.seen.add(cell)
        return appeared, vanished

    def state(self, cell: Cell) -> str:
        """"obsidian" | "portal" | "passable" | "solid" | "unknown"."""
        block = self.solid.get(cell)
        if block is None:
            return "passable" if cell in self.seen else "unknown"
        if block == OBSIDIAN:
            return "obsidian"
        if block == PORTAL:
            return "portal"
        return "passable" if block in PASSABLE else "solid"

    def obsidian(self) -> list[Cell]:
        return [c for c, b in self.solid.items() if b == OBSIDIAN]

    def portal_blocks(self) -> list[Cell]:
        return [c for c, b in self.solid.items() if b == PORTAL]


def parse_voxels(raw: Any, origin: Cell) -> dict[Cell, str] | None:
    """The engine's voxel answer as {absolute cell: block name}, or None if unreadable.

    None rather than {} on an unexpected shape: an empty dict is a legitimate answer
    (a box of nothing but air) and silently returning it would score every frame as
    missing while the run looked healthy. The callback logs the shape once and stops
    claiming to measure anything.
    """
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None
    if raw is None:
        return None
    if isinstance(raw, dict):
        # The other shape in the wild (`utils/vpt_lib/env_worker.py` reads
        # `info["voxels"]["block_name"]` as a 3-D array). Not what this engine's
        # EnvServer emits; refused loudly rather than guessed at.
        return None
    if not isinstance(raw, (list, tuple)):
        return None
    out: dict[Cell, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            return None
        try:
            cell = (origin[0] + int(item["x"]), origin[1] + int(item["y"]),
                    origin[2] + int(item["z"]))
        except (KeyError, TypeError, ValueError):
            return None
        block = str(item.get("type", "")) or "minecraft:unknown"
        if block in PASSABLE and block not in (FIRE, PORTAL):
            continue
        out[cell] = block
    return out


def fit(anchor: Cell, axis: str, world: World) -> FrameFit:
    """Score one candidate frame against what has been observed."""
    cells = frame_cells(anchor, axis)
    matched, missing, wrong, unknown = [], [], [], []
    for cell in cells.required:
        st = world.state(cell)
        if st == "obsidian":
            matched.append(cell)
        elif st == "unknown":
            unknown.append(cell)
            missing.append(cell)
        elif st in ("passable", "portal"):
            missing.append(cell)
        else:
            missing.append(cell)
            wrong.append(cell)
    blocked, lit = [], 0
    for cell in cells.interior:
        st = world.state(cell)
        if st == "portal":
            lit += 1
        elif st == "unknown":
            unknown.append(cell)
        elif st in ("obsidian", "solid"):
            blocked.append(cell)
    corners = sum(1 for c in cells.corners if world.state(c) in ("obsidian", "solid"))
    return FrameFit(anchor=anchor, axis=axis, matched=tuple(matched),
                    missing=tuple(missing), wrong_block=tuple(wrong),
                    blocked=tuple(blocked), unknown=tuple(unknown),
                    corners_present=corners, lit_cells=lit)


def candidates(world: World) -> list[tuple[Cell, str]]:
    """Every (anchor, axis) that would explain at least one placed obsidian block.

    Generated from the blocks rather than swept over space: ten obsidian give at most
    200 candidates, and the sweep would be the size of the pad cubed.
    """
    seeds: set[tuple[Cell, str]] = set()
    obs = world.obsidian()
    for axis in AXES:
        offsets = _required_offsets(axis)
        for cell in obs:
            for off in offsets:
                seeds.add(((cell[0] - off[0], cell[1] - off[1], cell[2] - off[2]), axis))
    # A lit portal proves its own frame even if the obsidian is out of the window.
    for cell in world.portal_blocks():
        for axis in AXES:
            u = _unit(axis)
            for i in range(INTERIOR_W):
                for j in range(INTERIOR_H):
                    seeds.add((_add(_add(cell, u, -i), (0, 1, 0), -j), axis))
    return sorted(seeds)


def best_fit(world: World) -> FrameFit | None:
    """The candidate frame the builder was evidently aiming at, or None if no obsidian.

    "Evidently aiming at" is `FrameFit.rank`: most required cells filled, fewest
    interior blockages, fewest unknowns. It is a best case for the agent -- if some
    other reading of the same blocks were closer to a portal, this returns that one --
    which is the right bias for a failure measurement.
    """
    best: FrameFit | None = None
    for anchor, axis in candidates(world):
        f = fit(anchor, axis, world)
        if best is None or f.rank() > best.rank():
            best = f
    return best


def stray_obsidian(world: World, best: FrameFit | None) -> list[Cell]:
    """Obsidian that is in no role in the best frame: blocks spent for nothing."""
    if best is None:
        return sorted(world.obsidian())
    cells = frame_cells(best.anchor, best.axis)
    part = set(cells.required) | set(cells.corners)
    return sorted(c for c in world.obsidian() if c not in part)


@dataclass
class Ignition:
    """One strike of the flint and steel, and the geometry at that instant."""

    step: int
    lit: bool
    fit: dict[str, Any]
    stray: list[list[int]]
    frame: str = ""          # path of the frame saved at this moment, if any


@dataclass
class PortalTrace:
    """The per-run record: what was placed where, when, and what it added up to.

    Everything here is host-side. It is written to `portal_report.json` at close and
    read by `scripts/portal_stats.py`; no field is ever forwarded to the agent.
    """

    window: tuple[int, ...] = (-8, 9, -5, 6, -8, 9)
    world: World = field(default_factory=World)
    placements: list[dict[str, Any]] = field(default_factory=list)
    removals: list[dict[str, Any]] = field(default_factory=list)
    ignitions: list[Ignition] = field(default_factory=list)
    samples: int = 0
    unreadable: int = 0
    first_complete_step: int | None = None
    first_lit_step: int | None = None
    origin: Cell | None = None
    dimension_step: int | None = None

    # -- ingestion -------------------------------------------------------------
    def observe(self, step: int, origin: Cell, raw: Any) -> bool:
        """Fold in one voxel answer. False when the answer could not be read.

        Refused outright once the dimension has changed. The map is keyed by absolute
        cell and the Nether's coordinates are the Overworld's over eight, so they do not
        collide -- they accumulate. And the Nether side of any portal is a
        game-generated, perfectly legal, already-lit frame, so `best_fit` would rank it
        above whatever the agent built and report the engine's own work as the arm's.
        Measured: without this refusal, runs that reached the Nether came back with
        `best_frame.anchor` at the NETHER portal, which made every one of their real
        placements score as "into a cell the frame does not use". The task is finished
        the moment the agent steps through, so nothing is lost by stopping here.
        """
        if self.dimension_step is not None:
            return False
        blocks = parse_voxels(raw, origin)
        if blocks is None:
            self.unreadable += 1
            return False
        self.samples += 1
        if self.origin is None:
            self.origin = tuple(origin)
        appeared, vanished = self.world.apply(origin, self.window, blocks)
        for cell, block in appeared:
            if block in (OBSIDIAN, PORTAL, FIRE):
                self.placements.append({"step": step, "cell": list(cell),
                                        "block": block})
        for cell, block in vanished:
            if block in (OBSIDIAN, PORTAL, FIRE):
                self.removals.append({"step": step, "cell": list(cell),
                                      "block": block})
        best = best_fit(self.world)
        if best is not None:
            if best.complete and self.first_complete_step is None:
                self.first_complete_step = step
            if best.lit and self.first_lit_step is None:
                self.first_lit_step = step
        return True

    def note_ignition(self, step: int, frame_path: str = "") -> Ignition:
        best = best_fit(self.world)
        ig = Ignition(step=step, lit=bool(best and best.lit),
                      fit=best.as_dict() if best else {},
                      stray=[list(c) for c in stray_obsidian(self.world, best)],
                      frame=frame_path)
        self.ignitions.append(ig)
        return ig

    # -- readout ---------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        best = best_fit(self.world)
        obsidian = sorted(self.world.obsidian())
        placed_obsidian = [p for p in self.placements if p["block"] == OBSIDIAN]
        mined_obsidian = [r for r in self.removals if r["block"] == OBSIDIAN]
        # The number the whole probe is for: how many obsidian placements went into a
        # cell the final frame does not use. `len(placed) - len(useful)` rather than a
        # per-placement test, because a cell can be filled, mined and refilled.
        useful = set()
        if best is not None:
            cells = frame_cells(best.anchor, best.axis)
            useful = set(cells.required) | set(cells.corners)
        wasted = [p for p in placed_obsidian if tuple(p["cell"]) not in useful]
        first = self.ignitions[0] if self.ignitions else None
        return {
            "samples": self.samples,
            "unreadable_samples": self.unreadable,
            "window": list(self.window),
            "origin": list(self.origin) if self.origin else None,
            "best_frame": best.as_dict() if best else None,
            "obsidian_now": [list(c) for c in obsidian],
            "stray_obsidian": [list(c) for c in stray_obsidian(self.world, best)],
            "placements": self.placements,
            "removals": self.removals,
            "counts": {
                "obsidian_placed": len(placed_obsidian),
                "obsidian_mined": len(mined_obsidian),
                "obsidian_placed_into_unused_cells": len(wasted),
                "ignitions": len(self.ignitions),
            },
            "ignitions": [vars(i) for i in self.ignitions],
            "first_ignition_matched": (first.fit.get("matched") if first else None),
            "first_complete_step": self.first_complete_step,
            "first_lit_step": self.first_lit_step,
            "dimension_change_step": self.dimension_step,
        }


def dimension_jump(start: tuple[float, float], now: tuple[float, float]) -> bool:
    """True when the coordinates say the player changed dimension.

    `location_stats.biome_id` reads 0 in both dimensions on this engine (a staged scene),
    so the signal is the coordinate scale: the Nether is the Overworld's
    x and z divided by eight. `macros_nether._dimcheck_tick` uses the same test, and
    this is the host-side copy of it so the report does not depend on the agent
    running that macro.
    """
    moved = math.dist(start, now) > 12.0
    shrank = abs(now[0]) < abs(start[0]) / 2.0 + 8 and abs(now[1]) < abs(start[1]) / 2.0 + 8
    return moved and shrank
