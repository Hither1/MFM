"""Previous lives: the records of earlier runs in this same world, carried into the MFM
arm's workspace (the MFM carry layer: the model pulls), and -- with `--sites` only -- the
places they verified pushed into the turn prompt.

Why. The benchmark's world is deterministic (seed 0, spawn (-3009.5, 71, -5572.5) in
every run), so what one run verified -- where the still water is, where a lava lake
sits, where an iron vein was mined, where a run died -- is true for the next. In 148
dragon runs no memory ever carried that to a later life: the worldmodel arms' relay
handed forward distilled documents (`--seed-memory`) that held nothing about obsidian
because no ancestor got there, the logbook relay handed a raw log the model did not
read, and the mfm arm's seeding skipped `episodes/`. The obsidian chain needs exactly
those coordinates: bucket first, then a LAKE the previous lives already saw, not a
blind corridor at y 8.

What this does, and nothing more:

    previous/life_<i>/         the earlier run's own record hard-linked in, oldest
                               first: logs.txt, episodes/, index.jsonl, grid.jsonl and
                               whatever the model wrote there (a worldmodel life's
                               documents); not its machinery (AGENTS.md, tools/,
                               attach/, previous/, sites.json). A seed dir that itself
                               carried lives contributes them first, so a chain of
                               relays keeps every generation.
    previous/index.jsonl       the earlier runs' episode indexes merged, paths rewritten
                               to previous/life_<i>/..., for ./tools/episodes.py --previous
    [KNOWN SITES]              (`--sites` only; NOT the MFM protocol -- the model is
                               fed what it should have read. Kept to reproduce the
                               ob1..obf3 chain of 2026-09-06, which ran with it.)
                               A block in the turn prompt: the places the earlier runs'
                               logs VERIFIED (a bucket filled here, lava filled the view
                               there, iron ore mined here, a death there), with the life
                               and step each comes from and the distance from where the
                               avatar stands now. Computed from the [NOTE]/[EVENT]/[STATE]
                               lines of their logs.txt -- no fact enters that a run did
                               not record itself.

Without `--sites` nothing of the earlier lives reaches the prompt: the contract says
where the records are and what they hold, and reading them is the model's own act
(`grep`, `./tools/episodes.py --previous`).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

#: What is NOT carried from an earlier run's memory dir: its machinery (the contract,
#: the tools, the per-turn attachment, the lives it carried itself -- `lives_of` expands
#: those -- and the harness's site digest). Everything else is that run's record: the
#: log, the episodes and their index, the grid, and whatever the model wrote there.
NOT_CARRIED = frozenset({"AGENTS.md", "CLAUDE.md", ".claude", "tools", "attach", "previous", "sites.json", "references",
                         "actions.json", "last_message.txt", "workspace.codexhome",
                         "previous_expedition_log.txt", "__pycache__"})

#: Sites of one kind within this distance are the same place (a pond has one shore
#: per approach; a lake is seen from several rims).
MERGE_RADIUS = {"water": 6.0, "lava": 6.0, "pour": 3.0, "obsidian": 3.0, "death": 4.0,
                "ore": 5.0}
#: A bucket filled within this distance of a lava sighting or a pour was that run's
#: own water scooped back, not a natural source (hd12z filled at (-2991, 11, -5565)).
OWN_WATER_RADIUS = 10.0
#: Under this share of the lower view a sighting is a sliver (a lava fall down a wall,
#: one source in a cave face), not a lake: ob1/ob1b (2026-09-06) both tunnelled to a 3%
#: sighting's pour rim, poured, and found stone. A lake reads 30% and more.
DEATH_WARN_RADIUS = 8.0
LAKE_FRAC = 0.08
#: A pour rim is "verified" when a lake-sized sighting stands within this distance.
POUR_VERIFY_RADIUS = 6.0

#: The ore blocks worth a line (what the milestones and the tools need).
ORE_BLOCKS = ("iron_ore", "coal_ore", "diamond_ore", "gravel", "gold_ore", "redstone_ore",
              "lapis_ore")

_HEADER = re.compile(r"^Action (\d+) \| Step (\d+)", re.M)
_STATE = re.compile(r"^\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\) pitch=(-?[\d.]+) "
                    r"yaw=(-?[\d.]+)", re.M)
_XYZ = r"\((-?\d+), (-?\d+), (-?\d+)\)"
_WATER_REACHED = re.compile(r"fetch_water: water reached at " + _XYZ)
_BUCKET_FILLED = re.compile(r"(?:fill_bucket|fetch_water): the bucket filled -- water_bucket")
_LAVA = re.compile(r"LAVA (?:AHEAD|FOUND): (?:it fills )?(\d+)% of the lower view(?: is lava)?"
                   r"(?: at " + _XYZ + r" facing yaw (-?\d+))?")
_POOL = re.compile(r"pool's near cell is about " + _XYZ)
_RIM = re.compile(r"RIM block to pour from is about " + _XYZ)
_POURED = re.compile(r"make_obsidian: done at the rim " + _XYZ)
_OBSIDIAN = re.compile(r"OBSIDIAN BROKEN at " + _XYZ)
_DIED = re.compile(r"YOU DIED at " + _XYZ)
#: A section in which the avatar was being hurt: the fire overlay of a burning avatar
#: reads as lava to the frame classifier (ob1_mfm 2026-09-06: "32% lava" at its own
#: feet while "still taking damage"; ob2_mfm went there, poured on stone and died).
_HURT = re.compile(r"took \d+ damage|still taking damage|lost \d+ health|YOU DIED|"
                   r"health \d+/20 is CRITICAL")
_EVENT = re.compile(r"^\[EVENT\] mine_block ([a-z_]+) \+(\d+)", re.M)

#: `--corridors`: a run of consecutive log sections at or below this y, each within
#: CORRIDOR_STEP blocks of the last, with no damage, no lava sighting and no death in
#: any of them, is a DRY CORRIDOR: ground a life dug through without incident. The
#: world is deterministic, so re-digging that line is safe; the tunnel itself is gone.
CORRIDOR_Y = 14.0
CORRIDOR_STEP = 8.0
CORRIDOR_MIN_BLOCKS = 8.0


class Corridor:
    __slots__ = ("life", "a", "b", "step0", "step1", "length", "sections")

    def __init__(self, life: int, a, b, step0: int, step1: int, length: float,
                 sections: int) -> None:
        self.life, self.a, self.b = life, tuple(a), tuple(b)
        self.step0, self.step1, self.length, self.sections = step0, step1, length, sections

    def dist(self, x: float, z: float) -> float:
        return min(math.hypot(self.a[0] - x, self.a[2] - z),
                   math.hypot(self.b[0] - x, self.b[2] - z))

    def as_dict(self) -> dict[str, Any]:
        return {"life": self.life, "a": list(self.a), "b": list(self.b),
                "step0": self.step0, "step1": self.step1, "length": round(self.length, 1),
                "sections": self.sections}


def corridors_from_log(log_text: str, life: int) -> list[Corridor]:
    """The dry corridors one run's log records (see CORRIDOR_Y)."""
    out: list[Corridor] = []
    run: list[tuple[int, tuple[float, float, float]]] = []
    length = 0.0

    def flush() -> None:
        nonlocal run, length
        if len(run) >= 3 and length >= CORRIDOR_MIN_BLOCKS:
            a, b = run[0][1], run[-1][1]
            out.append(Corridor(life, (round(a[0]), round(a[1]), round(a[2])),
                                (round(b[0]), round(b[1]), round(b[2])),
                                run[0][0], run[-1][0], length, len(run)))
        run, length = [], 0.0

    for step, sec in _sections(log_text):
        pos = _pos_of(sec)
        bad = (pos is None or pos[1] > CORRIDOR_Y or _HURT.search(sec) is not None
               or _LAVA.search(sec) is not None or _DIED.search(sec) is not None)
        if bad:
            flush()
            continue
        if run:
            last = run[-1][1]
            d = math.hypot(pos[0] - last[0], pos[2] - last[2])
            if d > CORRIDOR_STEP or abs(pos[1] - last[1]) > 3.0:
                flush()
                run.append((step, pos))
                continue
            length += d
        run.append((step, pos))
    flush()
    return out


def merge_corridors(cs: list[Corridor]) -> list[Corridor]:
    """Longest first; a corridor whose both ends lie within 4 blocks of a kept one's
    ends is the same line dug again."""
    kept: list[Corridor] = []
    for c in sorted(cs, key=lambda c: -c.length):
        dup = False
        for k in kept:
            ends = ((k.a, k.b), (k.b, k.a))
            if any(math.hypot(c.a[0] - p[0], c.a[2] - p[2]) <= 4.0
                   and math.hypot(c.b[0] - q[0], c.b[2] - q[2]) <= 4.0 for p, q in ends):
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept


def _link_tree(src: Path, dst: Path) -> int:
    n = 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        try:
            os.link(p, target)
        except OSError:
            shutil.copyfile(p, target)
        n += 1
    return n


def life_key(life: Path) -> str:
    """What makes a life the same life: its log's bytes. A carried copy under a seed's
    previous/ is a hard link (or a copy) of the original, so a path key would carry
    the six first-generation lives once per seed that carried them."""
    try:
        return hashlib.sha1((life / "logs.txt").read_bytes()).hexdigest()
    except OSError:
        return str(Path(life).resolve())


def lives_of(seed: Path) -> list[Path]:
    """The lives a seed memory dir brings: the lives it carried itself (oldest first),
    then the seed run's own record."""
    seed = Path(seed)
    out: list[Path] = []
    prev = seed / "previous"
    if prev.is_dir():
        for d in sorted(prev.glob("life_*"), key=lambda p: int(p.name.split("_")[1])):
            if (d / "logs.txt").exists():
                out.append(d)
    if (seed / "logs.txt").exists():
        out.append(seed)
    return out


class Site:
    __slots__ = ("kind", "x", "y", "z", "life", "step", "detail", "count", "frac",
                 "pool", "rim", "item")

    def __init__(self, kind: str, x: float, y: float | None, z: float, life: int, step: int,
                 detail: str = "", frac: float = 0.0, pool=None, rim=None, item: str = ""):
        self.kind, self.x, self.y, self.z = kind, float(x), (None if y is None else float(y)), float(z)
        self.life, self.step, self.detail, self.count = life, step, detail, 1
        self.frac, self.pool, self.rim, self.item = frac, pool, rim, item

    def dist(self, x: float, z: float) -> float:
        return math.hypot(self.x - x, self.z - z)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "x": self.x, "y": self.y, "z": self.z, "life": self.life,
                "step": self.step, "count": self.count, "frac": self.frac, "item": self.item,
                "pool": self.pool, "rim": self.rim, "detail": self.detail}


def _sections(log_text: str) -> list[tuple[int, str]]:
    """[(step, section text)] of a logs.txt."""
    parts = log_text.split("=" * 80)
    out = []
    for s in parts:
        m = _HEADER.search(s)
        if m:
            out.append((int(m.group(2)), s))
    return out


def _pos_of(section: str) -> tuple[float, float, float] | None:
    m = _STATE.search(section)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3))) if m else None


def sites_from_log(log_text: str, life: int) -> list[Site]:
    """Every site one run's log records, in order, unmerged."""
    out: list[Site] = []
    for step, sec in _sections(log_text):
        pos = _pos_of(sec)
        for m in _WATER_REACHED.finditer(sec):
            out.append(Site("water", int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            life, step, "fetch_water reached still water here"))
        if _BUCKET_FILLED.search(sec) and pos:
            out.append(Site("water", pos[0], pos[1], pos[2], life, step,
                            "a bucket was filled standing here"))
        hurt = _HURT.search(sec) is not None
        for m in _LAVA.finditer(sec):
            if hurt:
                continue          # a burning avatar's overlay, not a lake
            frac = float(m.group(1)) / 100.0
            if m.group(2) is not None:
                x, y, z, yaw = (int(m.group(2)), int(m.group(3)), int(m.group(4)),
                                int(m.group(5)))
            elif pos:
                x, y, z, yaw = pos[0], pos[1], pos[2], None
            else:
                continue
            pool = _POOL.search(sec)
            rim = _RIM.search(sec)
            if yaw is not None:
                yaw = int((yaw + 180) % 360 - 180)
            s = Site("lava", x, y, z, life, step,
                     f"lava filled {m.group(1)}% of the lower view standing here"
                     + (f", facing yaw {yaw}" if yaw is not None else ""), frac=frac,
                     pool=tuple(int(v) for v in pool.groups()) if pool else None,
                     rim=tuple(int(v) for v in rim.groups()) if rim else None)
            out.append(s)
        for m in _POURED.finditer(sec):
            out.append(Site("pour", int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            life, step, "a water bucket was poured on this RIM cell beside "
                                        "lava (make_obsidian ran to its end here)"))
        for m in _OBSIDIAN.finditer(sec):
            out.append(Site("obsidian", int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            life, step, "an OBSIDIAN block was broken here"))
        for m in _DIED.finditer(sec):
            out.append(Site("death", int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            life, step, "a run DIED here"))
        if pos:
            for m in _EVENT.finditer(sec):
                block, n = m.group(1), int(m.group(2))
                if block in ORE_BLOCKS:
                    out.append(Site("ore", pos[0], pos[1], pos[2], life, step,
                                    f"{block} mined standing here", item=block))
    return out


def merge_sites(sites: list[Site]) -> list[Site]:
    """One line per place: sites of a kind (and item) within MERGE_RADIUS are one
    site, counted; the lava line keeps the sighting with the largest view fraction,
    the others keep the first."""
    hot = [s for s in sites if s.kind in ("lava", "pour")]
    merged: list[Site] = []
    for s in sites:
        if s.kind == "water" and any(h.dist(s.x, s.z) <= OWN_WATER_RADIUS
                                     and s.y is not None and h.y is not None
                                     and abs(s.y - h.y) <= 6 for h in hot):
            continue
        r = MERGE_RADIUS.get(s.kind, 4.0)
        for m in merged:
            if m.kind == s.kind and m.item == s.item and m.dist(s.x, s.z) <= r:
                m.count += 1
                if s.kind == "lava" and s.frac > m.frac:
                    m.x, m.y, m.z, m.life, m.step = s.x, s.y, s.z, s.life, s.step
                    m.detail, m.frac = s.detail, s.frac
                    m.pool, m.rim = s.pool or m.pool, s.rim or m.rim
                elif s.kind == "lava":
                    m.pool, m.rim = m.pool or s.pool, m.rim or s.rim
                break
        else:
            merged.append(s)
    return merged


class PreviousLives:
    """The carried records and the sites they verified, for one workspace."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.dir = self.root / "previous"
        self.lives: list[Path] = []          # previous/life_<i> dirs, in order
        self.sources: list[str] = []         # where each life came from
        self.sites: list[Site] = []
        self.corridors: list[Corridor] = []
        self.rows: list[dict[str, Any]] = []
        self.linked = 0
        self.pushes = 0
        self.pushed_sites = False

    # -- seeding ----------------------------------------------------------------------

    def seed(self, seeds: list[Path], sites: bool = True) -> None:
        """Link the seeds' lives under previous/ and merge their indexes; with `sites`,
        read the places their logs verified (the [KNOWN SITES] block) as well."""
        self.pushed_sites = bool(sites)
        lives: list[Path] = []
        seen: set[str] = set()
        for seed in seeds:
            for life in lives_of(Path(seed)):
                key = life_key(life)
                if key in seen:
                    continue
                seen.add(key)
                lives.append(life)
        self.dir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        sites_: list[Site] = []
        corridors: list[Corridor] = []
        for i, src in enumerate(lives, start=1):
            dst = self.dir / f"life_{i}"
            for p in sorted(src.iterdir()):
                name = p.name
                if name in NOT_CARRIED or name.startswith("."):
                    continue
                if p.is_dir():
                    self.linked += _link_tree(p, dst / name)
                elif p.is_file():
                    (dst).mkdir(parents=True, exist_ok=True)
                    if not (dst / name).exists():
                        try:
                            os.link(p, dst / name)
                        except OSError:
                            shutil.copyfile(p, dst / name)
                    self.linked += 1
            self.lives.append(dst)
            self.sources.append(str(src))
            idx = src / "index.jsonl"
            if idx.exists():
                for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    r["life"] = i
                    for key in ("path", "image", "attachment"):
                        if r.get(key):
                            r[key] = f"previous/life_{i}/{r[key]}"
                    rows.append(r)
            try:
                text = (src / "logs.txt").read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if sites:
                sites_.extend(sites_from_log(text, i))
                corridors.extend(corridors_from_log(text, i))
        if rows:
            (self.dir / "index.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        self.rows = rows
        self.sites = merge_sites(sites_)
        self.corridors = merge_corridors(corridors)
        if sites:
            (self.dir / "sites.json").write_text(
                json.dumps({"lives": self.sources, "sites": [s.as_dict() for s in self.sites],
                            "corridors": [c.as_dict() for c in self.corridors]},
                           indent=1) + "\n", encoding="utf-8")
        logger.info(f"[previous] {len(self.lives)} live(s) carried ({self.linked} files "
                    f"linked, {len(rows)} indexed episodes), "
                    + (f"{len(self.sites)} sites pushed: "
                       + ", ".join(f"{k} x{n}" for k, n in sorted(
                           ((k, sum(1 for s in self.sites if s.kind == k))
                            for k in {s.kind for s in self.sites})))
                       if sites else "no sites pushed (the MFM carry: the model reads)"))

    # -- the block ----------------------------------------------------------------------

    def frame_for(self, life: int, step: int) -> str | None:
        """The carried episode image whose entry spans `step` in that life."""
        best = None
        for r in self.rows:
            if r.get("life") != life or not r.get("image"):
                continue
            a, b = int(r.get("first_step", -1)), int(r.get("last_step", -1))
            if a <= step <= max(a, b):
                return str(r["image"])
            if a <= step and (best is None or a > best[0]):
                best = (a, str(r["image"]))
        return best[1] if best else None

    def block(self, pos: dict[str, float] | None, inventory: dict[str, int],
              unmet: set[str], max_lines: int = 8, frames: bool = False,
              corridors: bool = False) -> str:
        """The [KNOWN SITES] block for this turn, "" when nothing is known."""
        if not self.sites and not (corridors and self.corridors):
            return ""
        have_water = int(inventory.get("water_bucket", 0) or 0) > 0
        have_bucket = have_water or int(inventory.get("bucket", 0) or 0) > 0
        obsidian_open = "mine_obsidian" in unmet
        iron_open = "mine_iron_ore" in unmet
        diamond_open = "mine_diamond_ore" in unmet

        lakes = [s for s in self.sites if s.kind == "lava" and s.frac >= LAKE_FRAC]

        def verified_pour(s: Site) -> bool:
            return any(l.dist(s.x, s.z) <= POUR_VERIFY_RADIUS for l in lakes)

        def rank(s: Site) -> tuple:
            # Lower sorts first. What the chain needs next comes first: water until
            # a filled bucket is carried, then the lava -- lakes, then pour rims a
            # lake stands beside, then slivers and unverified rims; ore while the
            # tools are missing.
            if s.kind in ("lava", "pour", "obsidian"):
                pri = 0 if (obsidian_open and have_water) else (2 if obsidian_open else 5)
                weak = ((s.kind == "lava" and s.frac < LAKE_FRAC)
                        or (s.kind == "pour" and not verified_pour(s)))
                return (pri + (1 if weak else 0), -s.frac, -s.count, s.step)
            elif s.kind == "water":
                pri = 0 if (obsidian_open and not have_water) else (2 if obsidian_open else 4)
            elif s.kind == "ore":
                if s.item == "iron_ore":
                    pri = 0 if iron_open else 3
                elif s.item == "diamond_ore":
                    pri = 0 if diamond_open else 3
                elif s.item == "gravel":
                    pri = 1 if "flint_and_steel" in unmet else 5
                else:
                    pri = 3
            else:
                pri = 7
            return (pri, -s.count, s.step)

        deaths = sorted((s for s in self.sites if s.kind == "death"),
                        key=lambda s: -s.count)[:2]
        ordered = sorted((s for s in self.sites if s.kind != "death"), key=rank)[:max_lines]
        ordered += deaths
        here = (float(pos["x"]), float(pos["z"])) if pos and pos.get("x") is not None else None
        all_deaths = [s for s in self.sites if s.kind == "death"]

        def died_near(s: Site) -> str:
            near = [d for d in all_deaths if d.dist(s.x, s.z) <= DEATH_WARN_RADIUS]
            if not near:
                return ""
            n = sum(d.count for d in near)
            return (f" WARNING: {n} previous " + ("life" if n == 1 else "lives")
                    + f" DIED within {DEATH_WARN_RADIUS:.0f} blocks of here (a dark cave: "
                      "mobs) -- torches placed, the sword one slot away, and the pour only "
                      "when LAVA AHEAD names the cells.")

        lines = []
        for s in ordered:
            where = (f"({s.x:.0f}, {s.y:.0f}, {s.z:.0f})" if s.y is not None
                     else f"({s.x:.0f}, ?, {s.z:.0f})")
            d = f", {s.dist(*here):.0f} blocks from you" if here else ""
            src = f"life {s.life} step {s.step}" + (f", x{s.count}" if s.count > 1 else "")
            if frames and s.kind in ("lava", "pour", "death", "water"):
                fr = self.frame_for(s.life, s.step)
                if fr:
                    src += f", frame={fr}"
            if s.kind == "lava":
                cells = ""
                if s.pool and s.rim:
                    cells = (f"; that sighting named pool cell {tuple(s.pool)} and rim "
                             f"{tuple(s.rim)}: stand where the sighting stood, facing the "
                             f"same way, and `make_obsidian({s.rim[0]}, {s.rim[1]}, "
                             f"{s.rim[2]})`")
                if s.frac >= LAKE_FRAC:
                    lines.append(f"- LAVA LAKE: {s.detail} at {where}{d} ({src}){cells}."
                                 + died_near(s))
                else:
                    lines.append(f"- LAVA SLIVER (not a lake: {100 * s.frac:.0f}% of the "
                                 f"view, one source or a fall): {s.detail} at {where}{d} "
                                 f"({src}){cells}.")
            elif s.kind == "water":
                lines.append(f"- STILL WATER: {s.detail} at {where}{d} ({src}).")
            elif s.kind == "pour":
                if verified_pour(s):
                    lines.append(f"- POUR RIM beside a lake: {s.detail} at {where}{d} ({src}) "
                                 f"-- stand within 3 blocks of it on the dry side and "
                                 f"`make_obsidian({s.x:.0f}, {s.y:.0f}, {s.z:.0f})`."
                                 + died_near(s))
                else:
                    lines.append(f"- POUR RIM, UNVERIFIED: {s.detail} at {where}{d} ({src}); "
                                 f"no lake-sized sighting stands beside it, and a pour there "
                                 f"proved nothing -- prefer a LAVA LAKE line.")
            elif s.kind == "obsidian":
                lines.append(f"- OBSIDIAN: {s.detail} at {where}{d} ({src}).")
            elif s.kind == "ore":
                lines.append(f"- ORE: {s.detail} at {where}{d} ({src}).")
            else:
                lines.append(f"- DEATH: {s.detail} at {where}{d} ({src}) -- lava or a fall; "
                             f"do not repeat that approach.")
        if corridors and self.corridors and here:
            deep_open = bool(unmet & {"mine_obsidian", "mine_diamond_ore", "mine_iron_ore"})
            if deep_open:
                for c in sorted(self.corridors, key=lambda c: c.dist(*here))[:3]:
                    lines.append(
                        f"- DRY CORRIDOR: life {c.life} tunnelled from {c.a} to {c.b} "
                        f"(steps {c.step0}-{c.step1}, {c.length:.0f} blocks over "
                        f"{c.sections} entries) with no lava, water or damage on the way, "
                        f"{c.dist(*here):.0f} blocks from you -- the tunnel is gone, but "
                        f"re-digging that line is safe ground.")
        self.pushes += 1
        n = len(self.lives)
        return ("[KNOWN SITES] from " + (f"{n} previous lives" if n != 1 else "1 previous life")
                + " in this same world, read by the harness from their own logs (under "
                "`previous/life_<i>/`). The world resets between lives: terrain, water, "
                "lava and ore stand as they were found; what a life built, dug or dropped "
                "is gone. Verify on arrival against [STATE]:\n" + "\n".join(lines))

    def audit(self) -> dict[str, Any]:
        return {"lives": len(self.lives), "sources": self.sources, "files_linked": self.linked,
                "sites": len(self.sites), "pushes": self.pushes,
                "kinds": {k: sum(1 for s in self.sites if s.kind == k)
                          for k in sorted({s.kind for s in self.sites})}}


#: The paragraph added to the mfm contract when lives are carried.
#: `--corridors`: appended to MFM_PREVIOUS_NOTE.
MFM_CORRIDOR_NOTE = """\
`[KNOWN SITES]` also lists DRY CORRIDORS: stretches an earlier life dug at or below y 14
with no lava, water or damage in any of its log sections. The tunnel itself does not
exist in this life, but the ground is the same, so tunnelling along that line
(`mine_forward` on its bearing, torches every 8 blocks) is the safe way down and
across; leave a corridor's line only for a named site."""

#: `--own` with previous lives: the digest is the model's own act (the user's rule of
#: 2026-09-07: no harness digest of earlier lives -- the model reads them and writes
#: what it takes from them, and that file is carried on with the rest of mine/).
MFM_DIGEST_NOTE = """\
Your first act in a life that has `previous/` is to DIGEST it yourself: read the lives'
`mine/notes.md` and scripts, their YOU DIED / LAVA AHEAD / obsidian / portal lines and
the places they verified, and write `mine/digest.md` -- the verified places with
coordinates, what each life died of and where, what its scripts assumed and whether
they worked, what you will do differently -- then keep it current as you learn. It is
carried to your next life with the rest of `mine/`; no summary of them is made for you.
"""

MFM_PREVIOUS_NOTE = """\
`previous/life_<i>/` holds the complete records of earlier runs in THIS SAME WORLD (same
seed, same spawn), oldest first: each one's `logs.txt` (the same [STATE]/[NOTE]/[EVENT]
vocabulary as yours), its `episodes/` with the frames and its `index.jsonl` where it
kept them (`./tools/episodes.py --previous --grep <text> | --near X Z | --tag ... `
queries all of them at once), and whatever that run wrote for itself. Nothing from
them is put in front of you: where an earlier life filled a bucket, where lava filled
its view, where it mined ore or died is in ITS log, and reading it (`grep -n` over
`previous/life_*/logs.txt`, or the query tool) is yours to do before searching blind.
The world resets between lives: terrain, water, lava and ore are exactly where they
were; nothing a life built, dug, placed or dropped survives, and step numbers in their
logs belong to THEIR run. Verify arrival at a remembered place against your live
[STATE]."""

#: `--sites`: the harness digests the carried logs into the [KNOWN SITES] block. Not
#: the MFM protocol (the model is handed what it should have read); the ob1..obf3 chain
#: of 2026-09-06 ran with it, and the flag reproduces that arm.
MFM_SITES_NOTE = """\
The harness reads the places those logs verified -- still water, lava lakes, ore,
deaths -- and puts them in the turn message as a `[KNOWN SITES]` block with the
distance from where you stand; it names the life and step behind each, so you can open
that log or frame. Go to a known site before searching blind."""

