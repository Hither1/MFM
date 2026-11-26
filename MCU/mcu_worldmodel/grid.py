"""The runner's own cell map: what it knows for certain, kept between turns and lives.

Measured on 148 dragon/diamond runs and the relay chain: 30-50% of blocked `go_to` targets were never
reached, the pond trap cost a median 612 steps per half run, and a remembered furnace
one cell off cost one run ~10k steps. In every case the runner had walked the ground it
needed -- from spawn to the pond, from the table to the shaft -- and threw the cells away
at the end of the tick. The observation is at human parity (frame + position + inventory,
no voxels), so this map records only what positions and the runner's own events prove:

  walked   a cell the avatar's feet stood in (exact); its head cell is air too
  floor    the cell under a walked cell (solid at the time)
  blocked  the cell ahead of a stalled walk, at feet level (a wall, a pit, a tree)
  water    where the frame showed water within reach, at feet level (approximate)
  lava     the pool and rim cells a LAVA AHEAD sighting named (approximate)
  hazard   where damage or a death was taken (exact position)
  placed   a table/furnace: the estimated cell AND the pose that placed or opened it
  opened   the exact pose (position, pitch, yaw) from which a screen actually opened

Routes are searched over walked cells only: two walked cells are neighbours when the
avatar stepped from one to the other, or when they are within one block on every axis.
That is the ground the avatar has stood on, so a route over it is walkable again in the
same life. Persisted as an append-only `grid.jsonl` beside the log (the sweep keeps it,
the carry layer links it), and rebuilt from it at start.
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Any, Iterable

Cell = tuple[int, int, int]

#: A walk that stalls records the cell this far ahead of the feet along the heading.
BLOCK_AHEAD = 1.0
#: A go_to detour is worth taking when it ends this much nearer the target than here.
DETOUR_GAIN = 2.0
#: Route search is capped at this many walked cells (a life walks a few thousand).
BFS_CAP = 20000
#: [MAP] radii: hazards and water named within these many blocks.
NEAR_HAZARD = 8.0
NEAR_WATER = 8.0
NEAR_LAVA = 12.0
#: A walked column at least this many consecutive levels deep under the cell ahead is an
#: open shaft (grid.drop_ahead); a fall of 4+ blocks hurts, of 23+ kills.
SHAFT_MIN_DROP = 4
#: `frontier` (off by default): ground counts as SEEN when it lies within this many blocks
#: (x, z) of a cell the avatar walked in the same dimension. An approximation -- a tunnel
#: sees less, a plateau more -- kept coarse on purpose: tiles of TILE x TILE columns.
SEEN_R = 24
TILE = 8
#: The eight bearings, with the yaw that faces them (+x is -sin yaw, +z is cos yaw).
BEARINGS = (("N", 0.0, -1.0, 180), ("NE", 0.7071, -0.7071, -135), ("E", 1.0, 0.0, -90),
            ("SE", 0.7071, 0.7071, -45), ("S", 0.0, 1.0, 0), ("SW", -0.7071, 0.7071, 45),
            ("W", -1.0, 0.0, 90), ("NW", -0.7071, -0.7071, 135))
#: Rays from the arrival cell stop here: past it a bearing is reported as seen to the cap.
RAY_CAP = 1024


def cell_of(pos: dict[str, float] | None) -> Cell | None:
    if not pos or pos.get("x") is None:
        return None
    try:
        return (int(math.floor(float(pos["x"]))), int(math.floor(float(pos["y"]))),
                int(math.floor(float(pos["z"]))))
    except (TypeError, ValueError):
        return None


def as_cell(seq) -> Cell:
    x, y, z = (int(v) for v in seq)
    return (x, y, z)


def centre(cell: Cell) -> tuple[float, float, float]:
    return (cell[0] + 0.5, float(cell[1]), cell[2] + 0.5)


def xz_dist(a: Cell, b: Cell) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _ahead(pos: dict[str, float], blocks: float = BLOCK_AHEAD) -> Cell | None:
    """The cell `blocks` ahead of the feet along the yaw (+x is -sin yaw, +z is cos yaw)."""
    c = cell_of(pos)
    if c is None:
        return None
    yaw = math.radians(float(pos.get("yaw", 0.0)))
    x = float(pos["x"]) - math.sin(yaw) * blocks
    z = float(pos["z"]) + math.cos(yaw) * blocks
    return (int(math.floor(x)), c[1], int(math.floor(z)))


class Grid:
    """Sparse cells keyed by absolute block coordinates, plus the walk's own edges."""

    KINDS = ("walked", "floor", "blocked", "water", "lava", "hazard", "placed", "opened")
    #: A tick that drops the feet faster than this is a FALL, not a walk, and its cell is
    #: not recorded: a fall reaches it after ~4 ticks (1.7 blocks), a jump's descent stays
    #: under it, a swim or a stair is far slower. One run (step 18768): a
    #: 13-block fall left mid-air cells on the map, `above()` took one two blocks up for
    #: the rim and queued pillar_up(2) at the bottom of the hole; routes would run through
    #: air. Standing ticks always record, so the landing cell is on the map.
    FALL_DY = 0.3

    def __init__(self, path: Path | str | None = None, frontier: bool = False) -> None:
        self.path = Path(path) if path else None
        #: `frontier`: also keep, per dimension, which ground has been SEEN (SEEN_R around
        #: the walked cells) and where it ends along eight bearings from the dimension's
        #: arrival cell -- i.e. where the avatar has NOT been. Walked rows then carry
        #: their dimension; off, grid.jsonl is byte-identical to before.
        self.frontier = bool(frontier)
        self.seen: dict[str, set[tuple[int, int]]] = {}     # dim -> seen tiles
        #: the same, from EARLIER lives' grid.jsonl in this world (carried under previous/)
        self.seen_prev: dict[str, set[tuple[int, int]]] = {}
        self.walked_tiles: dict[str, set[tuple[int, int]]] = {}
        self.anchor: dict[str, Cell] = {}                     # dim -> first walked cell
        self._coverage_emitted: dict[str, int] = {}           # dim -> tiles at last row
        self.walked: dict[Cell, dict[str, Any]] = {}     # cell -> {first, last, n}
        self.floor: set[Cell] = set()
        self.blocked: dict[Cell, int] = {}               # cell -> last step
        self.water: dict[Cell, int] = {}
        self.lava: dict[Cell, dict[str, Any]] = {}       # cell -> {step, frac, role}
        self.hazard: dict[Cell, dict[str, Any]] = {}     # cell -> {step, damage, kind}
        self.placed: dict[str, dict[str, Any]] = {}      # item -> {cell, pose, step}
        self.opened: dict[str, dict[str, Any]] = {}      # item -> {pose, step}
        self.edges: dict[Cell, set[Cell]] = {}           # consecutive feet cells
        self.trail: list[tuple[int, Cell]] = []          # (step, feet cell) on change
        self._last_cell: Cell | None = None
        self._last_pos: tuple[int, float] | None = None   # (step, y) of the last tick
        self._cols: dict[tuple[int, int], dict[int, dict[str, Any]]] = {}   # (x, z) -> {y: rec}
        self._cols_n = -1                                # len(walked) the index was built at
        self.events = 0
        if self.path is not None and self.path.exists():
            self._load()

    # ---------------- recording ----------------

    def _emit(self, kind: str, **rec: Any) -> None:
        self.events += 1
        if self.path is None:
            return
        rec = {"kind": kind, **rec}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        except OSError:
            pass

    def observe(self, step: int, pos: dict[str, float] | None, dim: str | None = None) -> None:
        """One tick's position: the feet cell is walked, the cell under it is floor.
        `dim` (frontier only): the dimension the feet are in; None = not known yet (a
        staged start before its teleport), and the cell then counts toward no coverage."""
        c = cell_of(pos)
        if c is None:
            return
        y = float(pos["y"])
        last, self._last_pos = self._last_pos, (int(step), y)
        if last is not None and int(step) - last[0] <= 2 and last[1] - y > self.FALL_DY:
            return                                      # mid-air: not ground anyone stood on
        if self.frontier and dim and dim not in self.anchor:
            # the first tick known to be in `dim` anchors it, standing still or not
            self._see(dim, c)
            self._emit("anchor", step=int(step), cell=list(c), dim=dim)
        rec = self.walked.get(c)
        if rec is None:
            self.walked[c] = {"first": int(step), "last": int(step), "n": 1}
            self.floor.add((c[0], c[1] - 1, c[2]))
            new = True
        else:
            rec["last"] = int(step)
            new = c != self._last_cell
            if new:
                rec["n"] += 1
        if c != self._last_cell:
            last = self._last_cell
            if last is not None and max(abs(c[0] - last[0]), abs(c[1] - last[1]),
                                        abs(c[2] - last[2])) <= 2:
                # Consecutive ticks: a step, never a teleport (a death or a portal
                # jumps 15+ blocks and is not a walk anyone can repeat).
                self.edges.setdefault(last, set()).add(c)
                self.edges.setdefault(c, set()).add(last)
            self.trail.append((int(step), c))
            if self.frontier and dim:
                self._see(dim, c)
                self._emit("walked", step=int(step), cell=list(c), dim=dim)
            else:
                self._emit("walked", step=int(step), cell=list(c))
            self._last_cell = c

    # ---------------- frontier: where the avatar has not been ----------------

    @staticmethod
    def _tile(x: float, z: float) -> tuple[int, int]:
        return (int(math.floor(x / TILE)), int(math.floor(z / TILE)))

    def _see(self, dim: str, c: Cell) -> None:
        self.anchor.setdefault(dim, c)
        wt = self.walked_tiles.setdefault(dim, set())
        t = self._tile(c[0], c[2])
        if t in wt:
            return
        wt.add(t)
        self.seen.setdefault(dim, set()).update(self._disk(t))

    @staticmethod
    def _disk(t: tuple[int, int]) -> list[tuple[int, int]]:
        """The tiles within SEEN_R of tile t's centre."""
        cx, cz = (t[0] + 0.5) * TILE, (t[1] + 0.5) * TILE
        k = SEEN_R // TILE + 1
        return [(i, j) for i in range(t[0] - k, t[0] + k + 1)
                for j in range(t[1] - k, t[1] + k + 1)
                if math.hypot((i + 0.5) * TILE - cx, (j + 0.5) * TILE - cz) <= SEEN_R]

    def seed_seen(self, path: Path | str) -> int:
        """Ground an EARLIER life saw in this same world: its grid.jsonl's walked rows that
        carry a dimension (a frontier life's). Counted as seen, never as walked: routes,
        anchors and this life's own record are untouched. Returns the tiles added."""
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return 0
        done: dict[str, set[tuple[int, int]]] = {}
        before = sum(len(v) for v in self.seen_prev.values())
        for line in lines:
            if '"walked"' not in line or '"dim"' not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("kind") != "walked" or not r.get("dim") or not r.get("cell"):
                continue
            t = self._tile(r["cell"][0], r["cell"][2])
            d = done.setdefault(str(r["dim"]), set())
            if t in d:
                continue
            d.add(t)
            self.seen_prev.setdefault(str(r["dim"]), set()).update(self._disk(t))
        return sum(len(v) for v in self.seen_prev.values()) - before

    def is_seen(self, dim: str, x: float, z: float) -> bool:
        t = self._tile(x, z)
        return t in self.seen.get(dim, ()) or t in self.seen_prev.get(dim, ())

    def coverage(self, dim: str) -> dict[str, Any] | None:
        """Along each of eight bearings from the dimension's arrival cell, how far the seen
        ground runs unbroken and the first unseen point; None before any walked cell."""
        a = self.anchor.get(dim)
        if a is None:
            return None
        ax, az = a[0] + 0.5, a[2] + 0.5
        rays = {}
        for name, ux, uz, yaw in BEARINGS:
            d = 0
            while d < RAY_CAP and self.is_seen(dim, ax + ux * d, az + uz * d):
                d += TILE // 2
            rays[name] = {"seen_to": d, "yaw": yaw,
                          "unseen_at": None if d >= RAY_CAP else
                          [int(round(ax + ux * d)), int(round(az + uz * d))]}
        mine, prev = self.seen.get(dim, set()), self.seen_prev.get(dim, set())
        return {"dim": dim, "anchor": list(a), "tiles": len(mine | prev),
                "earlier_tiles": len(prev - mine),
                "walked_tiles": len(self.walked_tiles.get(dim, ())), "rays": rays}

    def note_coverage(self, step: int, dim: str | None) -> dict[str, Any] | None:
        """A `coverage` row in grid.jsonl for `dim` when its seen ground grew since the
        last row (once per turn at most: the caller is the turn prompt)."""
        if not self.frontier or not dim:
            return None
        cov = self.coverage(dim)
        if cov is None or self._coverage_emitted.get(dim) == cov["tiles"]:
            return cov
        self._coverage_emitted[dim] = cov["tiles"]
        self._emit("coverage", step=int(step), dim=dim, anchor=cov["anchor"],
                   tiles=cov["tiles"],
                   seen_to={k: r["seen_to"] for k, r in cov["rays"].items()},
                   unseen_at={k: r["unseen_at"] for k, r in cov["rays"].items()})
        return cov

    def frontier_lines(self, pos: dict[str, float] | None, dim: str | None) -> list[str]:
        """The [MAP] lines that say where the avatar has NOT been in this dimension."""
        if not self.frontier or not dim:
            return []
        cov = self.coverage(dim)
        here = cell_of(pos)
        if cov is None or here is None:
            return []
        a = tuple(cov["anchor"])
        rays = cov["rays"]
        parts = []
        for name, r in rays.items():
            u = r["unseen_at"]
            parts.append(f"{name} {r['seen_to']}" + (f" -> ({u[0]}, {u[1]})" if u else "+"))
        short = [n for n, r in rays.items() if r["seen_to"] <= SEEN_R + TILE]
        who = ("you or an earlier life (previous/*/grid.jsonl)" if cov.get("earlier_tiles")
               else "you")
        out = [f"- Seen ground in {dim} (approximate: tiles within {SEEN_R} blocks of a cell "
               f"{who} walked there; {cov['tiles']} tiles of {TILE}x{TILE}"
               + (f", {cov['earlier_tiles']} of them only by earlier lives"
                  if cov.get("earlier_tiles") else "") + "): from your arrival "
               f"cell {a} ({xz_dist(here, a):.0f} blocks from you), the seen ground runs, "
               f"by bearing (N = -z, E = +x), blocks -> first unseen point: "
               + "; ".join(parts) + "."]
        if short:
            out.append(f"- Never seen more than {SEEN_R + TILE} blocks from the arrival cell, "
                       f"along: {', '.join(short)} (yaw "
                       + ", ".join(str(rays[n]['yaw']) for n in short)
                       + "). `coverage` rows in grid.jsonl hold every update.")
        return out

    def mark_blocked(self, step: int, pos: dict[str, float] | None) -> Cell | None:
        c = _ahead(pos) if pos else None
        if c is None:
            return None
        self.blocked[c] = int(step)
        self._emit("blocked", step=int(step), cell=list(c))
        return c

    def mark_water(self, step: int, x: float, z: float, y: float) -> Cell:
        c = (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
        if c not in self.water:
            self._emit("water", step=int(step), cell=list(c))
        self.water[c] = int(step)
        return c

    def mark_lava(self, step: int, pool: Cell | None, rim: Cell | None,
                  frac: float) -> None:
        for role, c in (("pool", pool), ("rim", rim)):
            if c is None:
                continue
            c = as_cell(c)
            self.lava[c] = {"step": int(step), "frac": float(frac), "role": role}
            self._emit("lava", step=int(step), cell=list(c), frac=float(frac), role=role)

    def mark_hazard(self, step: int, pos: dict[str, float] | None, damage: float,
                    kind: str = "damage") -> None:
        c = cell_of(pos)
        if c is None:
            return
        prev = self.hazard.get(c)
        total = float(damage) + (float(prev["damage"]) if prev else 0.0)
        self.hazard[c] = {"step": int(step), "damage": total, "kind": kind}
        self._emit("hazard", step=int(step), cell=list(c), damage=float(damage), what=kind)

    @staticmethod
    def pose_of(pos: dict[str, float] | None) -> dict[str, float] | None:
        if not pos or pos.get("x") is None:
            return None
        return {"x": round(float(pos["x"]), 2), "y": round(float(pos["y"]), 2),
                "z": round(float(pos["z"]), 2), "pitch": round(float(pos.get("pitch", 0.0)), 1),
                "yaw": round(float(pos.get("yaw", 0.0)), 1)}

    def mark_placed(self, step: int, item: str, cell: Cell | None,
                    pos: dict[str, float] | None) -> None:
        pose = self.pose_of(pos)
        self.placed[str(item)] = {"cell": tuple(cell) if cell else None, "pose": pose,
                                  "step": int(step)}
        self._emit("placed", step=int(step), item=str(item),
                   cell=list(cell) if cell else None, pose=pose)

    def mark_opened(self, step: int, item: str, pos: dict[str, float] | None) -> None:
        """The pose a screen actually opened from: the thing to replay, not the cell."""
        pose = self.pose_of(pos)
        if pose is None:
            return
        self.opened[str(item)] = {"pose": pose, "step": int(step)}
        self._emit("opened", step=int(step), item=str(item), pose=pose)

    # ---------------- queries ----------------

    def neighbours(self, c: Cell) -> Iterable[Cell]:
        seen = set(self.edges.get(c, ()))
        for n in seen:
            yield n
        x, y, z = c
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == 0 and dz == 0:
                    continue
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy, z + dz)
                    if n in self.walked and n not in seen:
                        yield n

    def bfs(self, start: Cell, goal=None, limit: int = BFS_CAP
            ) -> tuple[dict[Cell, Cell | None], Cell | None]:
        """Parents over walked cells from `start`; stops at the first cell `goal(c)`."""
        if start not in self.walked:
            near = self.nearest_walked(start)
            if near is None:
                return {}, None
            start = near
        parents: dict[Cell, Cell | None] = {start: None}
        q = deque([start])
        while q and len(parents) <= limit:
            c = q.popleft()
            if goal is not None and goal(c):
                return parents, c
            for n in self.neighbours(c):
                if n not in parents:
                    parents[n] = c
                    q.append(n)
        return parents, None

    @staticmethod
    def path_to(parents: dict[Cell, Cell | None], end: Cell) -> list[Cell]:
        out = [end]
        while True:
            back = parents.get(out[-1])
            if back is None:
                break
            out.append(back)
        out.reverse()
        return out

    def nearest_walked(self, c: Cell, radius: int = 2) -> Cell | None:
        best, bd = None, 1e9
        for w in self.walked:
            d = max(abs(w[0] - c[0]), abs(w[1] - c[1]), abs(w[2] - c[2]))
            if d <= radius and d < bd:
                best, bd = w, d
        return best

    def detour(self, pos: dict[str, float] | None, tx: float, tz: float
               ) -> list[Cell] | None:
        """A walked route from here to the walked cell nearest the target (x, z), when
        that cell is at least DETOUR_GAIN blocks nearer than where the walk stalled."""
        here = cell_of(pos)
        if here is None or not self.walked:
            return None
        parents, _ = self.bfs(here)
        if not parents:
            return None
        tcell = (int(math.floor(tx)), here[1], int(math.floor(tz)))
        best, bd = None, xz_dist(here, tcell) - DETOUR_GAIN
        for c in parents:
            d = xz_dist(c, tcell)
            if d < bd:
                best, bd = c, d
        if best is None:
            return None
        path = self.path_to(parents, best)
        return path[1:] if len(path) > 1 else None

    def escape_from_water(self, pos: dict[str, float] | None, min_dist: float
                          ) -> list[Cell] | None:
        """The shortest walked route to a walked cell at least `min_dist` blocks (in x, z)
        from every known water cell, or None."""
        here = cell_of(pos)
        if here is None or not self.walked or not self.water:
            return None
        water = list(self.water)

        def dry(c: Cell) -> bool:
            return all(xz_dist(c, w) >= min_dist for w in water)

        parents, end = self.bfs(here, goal=dry)
        if end is None:
            return None
        path = self.path_to(parents, end)
        return path[1:] if len(path) > 1 else None

    def above(self, pos: dict[str, float] | None, radius: float = 6.0, min_rise: int = 2,
              max_rise: int = 8) -> tuple[Cell, int] | None:
        """The nearest walked cell within `radius` (x, z) that stands `min_rise`+ blocks
        HIGHER than the avatar -- the rim of the hole it walked or fell into, which its
        walk cannot climb (a 2-block rise has no edge on the map). None on level ground.
        31% of 1,387 blocked walks in 208 runs were made from such a hole (pitstalls.py).
        A cell more than `max_rise` higher is not a rim but the mouth of the shaft the
        avatar came down (one run: "44 blocks below" the y 55 trail while walking
        one block at y 11 -- pillar_up(6) reaches nothing up there)."""
        here = cell_of(pos)
        if here is None or not self.walked:
            return None
        best = None
        for c in self.walked:
            rise = c[1] - here[1]
            if rise < min_rise or rise > max_rise:
                continue
            d = xz_dist(c, here)
            if d <= radius and (best is None or d < best[1]):
                best = (c, d, rise)
        return (best[0], int(best[2])) if best else None

    def _column(self, x: int, z: int) -> dict[int, dict[str, Any]]:
        """The walked levels of column (x, z), {y: record}; the index is rebuilt when a
        walked cell was added (every few ticks on a walk: a few thousand cells)."""
        if self._cols_n != len(self.walked):
            cols: dict[tuple[int, int], dict[int, dict[str, Any]]] = {}
            for c, r in self.walked.items():
                cols.setdefault((c[0], c[2]), {})[c[1]] = r
            self._cols, self._cols_n = cols, len(self.walked)
        return self._cols.get((x, z), {})

    def drop_ahead(self, cell: Cell, min_drop: int = SHAFT_MIN_DROP) -> dict[str, Any] | None:
        """The open shaft under `cell` (a feet cell the avatar is about to step into), or
        None. A shaft is a column (x, z) of walked cells on CONSECUTIVE levels -- the
        avatar's own dig_down records every level on the way down (one run's y 9..67 column
        at (-3005, -5581): 59 levels) -- whose top is the cell or the one under it and
        whose bottom lies `min_drop`+ blocks lower. The column's LAST traversal must have
        gone down: a pillar_up leaves the same levels, solid, walked upward last, and so
        does a shaft the avatar pillared back out of. A staircase is one level per column
        and a fall records no intermediate levels: neither is a shaft here.
        One run (step 19286): mine_forward north from a stair at y 67 broke into
        its own shaft and the avatar fell 58 blocks onto the drops it had come for;
        one run died the same way. Neither was told: the column was in this map."""
        x, y, z = cell
        col = self._column(x, z)
        if not col:
            return None
        top = max((lv for lv in col if lv <= y), default=None)
        if top is None or top < y - 1:
            return None
        bottom = top
        while bottom - 1 in col:
            bottom -= 1
        drop = y - bottom
        if drop < min_drop:
            return None
        if col[bottom]["last"] < col[top]["last"]:
            return None                     # walked upward last: pillared, solid
        return {"top": top, "bottom": bottom, "drop": drop,
                "dug": int(col[top]["first"]), "reached": int(col[bottom]["first"])}

    def route(self, pos: dict[str, float] | None, target: Cell) -> list[Cell] | None:
        """The walked route from here to the walked cell nearest `target` (within 2)."""
        here = cell_of(pos)
        if here is None:
            return None
        goal_cell = self.nearest_walked(target, radius=2)
        if goal_cell is None:
            return None
        parents, end = self.bfs(here, goal=lambda c: c == goal_cell)
        if end is None:
            return None
        path = self.path_to(parents, end)
        return path[1:] if len(path) > 1 else []

    def last_productive(self) -> Cell | None:
        return self.trail[-1][1] if self.trail else None

    # ---------------- the [MAP] block ----------------

    def summary(self, pos: dict[str, float] | None, step: int, max_lines: int = 6,
                dim: str | None = None) -> str:
        """Five or six lines the model can act on; "" before the first position."""
        here = cell_of(pos)
        if here is None or not self.walked:
            return ""
        lines = [f"- You stand in cell {here}; {len(self.walked)} cells walked this life "
                 f"(a route over them is walkable again)."]
        for item, rec in sorted(self.placed.items()):
            cell = rec.get("cell")
            op = self.opened.get(item)
            pose = (op or rec).get("pose") or {}
            if cell is None and not pose:
                continue
            d = xz_dist(here, tuple(cell)) if cell else math.hypot(
                here[0] + 0.5 - pose["x"], here[2] + 0.5 - pose["z"])
            how = (f"opened from ({pose['x']:.1f}, {pose['y']:.0f}, {pose['z']:.1f}) "
                   f"pitch {pose['pitch']:.0f} yaw {pose['yaw']:.0f}" if op else
                   f"placed from ({pose['x']:.1f}, {pose['y']:.0f}, {pose['z']:.1f})"
                   if pose else "cell only")
            rt = self.route(pos, tuple(cell)) if cell else None
            via = (f"; walked route: {len(rt)} cells" if rt else
                   "; no walked route on record" if rt is None else "; you are beside it")
            lines.append(f"- {item}: cell {tuple(cell) if cell else '?'}, {d:.0f} blocks away, "
                         f"{how}{via}. `use_at` on its cell opens it.")
        if self.water:
            near = sorted(self.water, key=lambda c: xz_dist(here, c))[:1]
            d = xz_dist(here, near[0])
            if d <= NEAR_WATER:
                esc = self.escape_from_water(pos, NEAR_WATER)
                lines.append(f"- WATER {d:.0f} blocks away at {near[0]}"
                             + (f"; the dry walked cell nearest you is {esc[-1]}, "
                                f"{len(esc)} cells along your own trail (dig_down's water "
                                f"refusal walks you there)." if esc else
                                "; no walked cell 8+ blocks from it yet -- walk away "
                                "along open ground first."))
            else:
                lines.append(f"- Nearest known water {d:.0f} blocks away at {near[0]}.")
        hz = [(c, r) for c, r in self.hazard.items() if xz_dist(here, c) <= NEAR_HAZARD
              and abs(c[1] - here[1]) <= 6]
        if hz:
            hz.sort(key=lambda cr: -cr[1]["damage"])
            c, r = hz[0]
            lines.append(f"- DANGER within {NEAR_HAZARD:.0f} blocks: {r['kind']} at {c} "
                         f"({r['damage']:.0f} hp so far, step {r['step']})"
                         + (f"; {len(hz)} such cells" if len(hz) > 1 else "") + ".")
        lv = [(c, r) for c, r in self.lava.items() if xz_dist(here, c) <= NEAR_LAVA]
        if lv:
            lv.sort(key=lambda cr: xz_dist(here, cr[0]))
            c, r = lv[0]
            lines.append(f"- LAVA {r['role']} cell {c}, {xz_dist(here, c):.0f} blocks away "
                         f"(sighting {100 * r['frac']:.0f}%, step {r['step']}).")
        bl = [c for c, s in self.blocked.items() if xz_dist(here, c) <= 3.0
              and step - s <= 2000]
        if bl:
            lines.append(f"- Walks stalled beside you at {bl[:3]}: those cells are solid "
                         f"or a drop; `go_to` now detours over walked cells by itself.")
        fr = self.frontier_lines(pos, dim)
        return "\n".join(lines[:max_lines] + fr)

    # ---------------- persistence ----------------

    def _load(self) -> None:
        if self.path is None:
            return
        try:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = r.get("kind")
            cell = as_cell(r["cell"]) if r.get("cell") else None
            step = int(r.get("step", 0))
            if kind == "walked" and cell:
                rec = self.walked.get(cell)
                if rec is None:
                    self.walked[cell] = {"first": step, "last": step, "n": 1}
                    self.floor.add((cell[0], cell[1] - 1, cell[2]))
                else:
                    rec["last"] = step
                    rec["n"] += 1
                last = self._last_cell
                if last is not None and last != cell and max(
                        abs(cell[0] - last[0]), abs(cell[1] - last[1]),
                        abs(cell[2] - last[2])) <= 2:
                    self.edges.setdefault(last, set()).add(cell)
                    self.edges.setdefault(cell, set()).add(last)
                self.trail.append((step, cell))
                self._last_cell = cell
                if self.frontier and r.get("dim"):
                    self._see(str(r["dim"]), cell)
            elif kind == "anchor" and cell and r.get("dim") and self.frontier:
                self._see(str(r["dim"]), cell)
            elif kind == "coverage" and r.get("dim"):
                self._coverage_emitted[str(r["dim"])] = int(r.get("tiles", -1))
            elif kind == "blocked" and cell:
                self.blocked[cell] = step
            elif kind == "water" and cell:
                self.water[cell] = step
            elif kind == "lava" and cell:
                self.lava[cell] = {"step": step, "frac": float(r.get("frac", 0.0)),
                                   "role": r.get("role", "pool")}
            elif kind == "hazard" and cell:
                prev = self.hazard.get(cell)
                self.hazard[cell] = {"step": step, "kind": r.get("what", "damage"),
                                     "damage": float(r.get("damage", 0.0))
                                     + (prev["damage"] if prev else 0.0)}
            elif kind == "placed":
                self.placed[str(r.get("item"))] = {"cell": cell, "pose": r.get("pose"),
                                                   "step": step}
            elif kind == "opened":
                self.opened[str(r.get("item"))] = {"pose": r.get("pose"), "step": step}

    def audit(self) -> dict[str, Any]:
        return {"walked": len(self.walked), "blocked": len(self.blocked),
                "water": len(self.water), "lava": len(self.lava),
                "hazard": len(self.hazard), "placed": sorted(self.placed),
                "opened": sorted(self.opened), "events": self.events,
                **({"frontier": {d: {"tiles": len(t), "walked_tiles": len(self.walked_tiles.get(d, ())),
                                     "seen_to": {k: r["seen_to"] for k, r in
                                                 (self.coverage(d) or {}).get("rays", {}).items()}}
                                 for d, t in sorted(self.seen.items())}} if self.frontier else {})}
