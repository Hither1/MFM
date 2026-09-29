"""Previous lives: the records of earlier runs in this same world, carried into the MFM
arm's workspace. The model pulls: nothing of them is put into the turn prompt.

Why. The benchmark's world is deterministic for a given seed, so what one run verified
-- where the still water is, where a lava lake sits, where an iron vein was mined,
where a run died -- is true for the next run in that world.

What this does, and nothing more:

    previous/life_<i>/         the earlier run's own record hard-linked in, oldest
                               first: logs.txt, episodes/, index.jsonl, grid.jsonl and
                               whatever the model wrote there (its `mine/`); not its
                               machinery (AGENTS.md, tools/, attach/, previous/). A
                               seed dir that itself carried lives contributes them
                               first, so a chain of relays keeps every generation.
    previous/index.jsonl       the earlier runs' episode indexes merged, paths rewritten
                               to previous/life_<i>/..., for ./tools/episodes.py --previous

The contract says where the records are and what they hold, and reading them is the
model's own act (`grep`, `./tools/episodes.py --previous`).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

#: What is NOT carried from an earlier run's memory dir: its machinery (the contract,
#: the tools, the per-turn attachment, the lives it carried itself -- `lives_of` expands
#: those). Everything else is that run's record: the
#: log, the episodes and their index, the grid, and whatever the model wrote there.
NOT_CARRIED = frozenset({"AGENTS.md", "CLAUDE.md", ".claude", "tools", "attach", "previous", "sites.json", "references",
                         "actions.json", "last_message.txt", "workspace.codexhome",
                         "previous_expedition_log.txt", "__pycache__"})

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


class PreviousLives:
    """The carried records of one workspace."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.dir = self.root / "previous"
        self.lives: list[Path] = []          # previous/life_<i> dirs, in order
        self.sources: list[str] = []         # where each life came from
        self.rows: list[dict[str, Any]] = []
        self.linked = 0

    def seed(self, seeds: list[Path]) -> None:
        """Link the seeds' lives under previous/ and merge their indexes."""
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
        if rows:
            (self.dir / "index.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        self.rows = rows
        logger.info(f"[previous] {len(self.lives)} live(s) carried ({self.linked} files "
                    f"linked, {len(rows)} indexed episodes)")

    def audit(self) -> dict[str, Any]:
        return {"lives": len(self.lives), "sources": self.sources, "files_linked": self.linked}


#: `own` with previous lives: the digest is the model's own act (no harness digest of
#: earlier lives -- the model reads them and writes what it takes from them, and that
#: file is carried on with the rest of mine/).
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
