"""Previous lives: the records of earlier runs in this same world, carried into the MFM
arm's workspace (the MFM carry layer: the model pulls).

Why. The benchmark's world is deterministic (seed 0, spawn (-3009.5, 71, -5572.5) in
every run), so what one run verified -- where the still water is, where a lava lake
sits, where an iron vein was mined, where a run died -- is true for the next. In 148
dragon runs no memory ever carried that to a later life: the logbook relay handed a raw
log the model did not read, and the mfm arm's seeding skipped `episodes/`. The obsidian
chain needs exactly those coordinates: bucket first, then a LAKE the previous lives
already saw, not a blind corridor at y 8.

What this does, and nothing more:

    previous/life_<i>/         the earlier run's own record hard-linked in, oldest
                               first: logs.txt, episodes/, index.jsonl, grid.jsonl and
                               whatever the model wrote there; not its machinery
                               (AGENTS.md, tools/, attach/, previous/). A seed dir that
                               itself carried lives contributes them first, so a chain
                               of relays keeps every generation.
    previous/index.jsonl       the earlier runs' episode indexes merged, paths rewritten
                               to previous/life_<i>/..., for ./tools/episodes.py --previous

Nothing of the earlier lives reaches the prompt: the contract says where the records are
and what they hold, and reading them is the model's own act (`grep`,
`./tools/episodes.py --previous`). The harness digest of those logs into a [KNOWN SITES]
block (`--sites`, `--corridors`) was removed on 2026-09-21: it was never the MFM
protocol and no arm since the ob chain of 2026-09-06 ran with it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from loguru import logger

from mfm.memory.carry import CarriedRecord, seed_previous

#: What is NOT carried from an earlier run's memory dir: its machinery (the contract,
#: the tools, the per-turn attachment, the lives it carried itself -- `lives_of` expands
#: those -- and the harness's site digest). Everything else is that run's record: the
#: log, the episodes and their index, the grid, and whatever the model wrote there.
NOT_CARRIED = frozenset({"AGENTS.md", "tools", "attach", "previous", "sites.json", "references",
                         "skills",      # the harness skill package of that life (its texts change between generations)
                         "actions.json", "last_message.txt", "workspace.codexhome",
                         "previous_expedition_log.txt", "__pycache__"})

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
    """The carried records, for one workspace."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.dir = self.root / "previous"
        self.lives: list[Path] = []          # previous/life_<i> dirs, in order
        self.sources: list[str] = []         # where each life came from
        self.rows: list[dict[str, Any]] = []
        self.linked = 0

    # -- seeding ----------------------------------------------------------------------

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
        # The linking and the index merge are the MFM carry layer's, shared with KiCad
        # (mfm.memory.carry.seed_previous): a life is one carried record, named
        # `life_<i>`, and its rows are stamped `life`.
        records = [CarriedRecord(name=f"life_{i}", source=src, tag={"life": i})
                   for i, src in enumerate(lives, start=1)]
        seed = seed_previous(self.dir, records, skip=NOT_CARRIED, skip_hidden=True,
                             write_index=False)
        self.linked += seed.linked
        rows = seed.rows
        self.lives.extend(self.dir / r.name for r in records)
        self.sources.extend(str(r.source) for r in records)
        by_life = dict(enumerate(lives, start=1))
        for r in rows:
            # A life recorded before the index carried its outcome (the store writes
            # note/events/inventory_delta into the row since 2026-09-09): read
            # outcome.json once here, so `--grep`/`--ores` over previous/ never open a
            # file (85-120 s over a 2,800-episode life otherwise). The row's path has
            # already been rewritten to previous/life_<i>/..., so strip that to find
            # the file in the SOURCE life.
            i = r.get("life")
            src = by_life.get(i)
            if src is None or "events" in r or not r.get("path"):
                continue
            rel = str(r["path"]).replace(f"previous/life_{i}/", "", 1)
            try:
                oc = json.loads((src / rel / "outcome.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                oc = {}
            r["events"] = [str(e) for e in (oc.get("events") or [])][:12]
            notes = oc.get("notes") or []
            if notes:
                r["note"] = " ".join(str(notes[0]).split())[:220]
            delta = oc.get("inventory_delta")
            if isinstance(delta, dict) and delta:
                r["inventory_delta"] = dict(list(delta.items())[:12])
        # Written here rather than by seed_previous, so the index on disk carries the
        # enrichment above and `self.rows` is exactly what a reader will find.
        if rows:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / "index.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
                encoding="utf-8")
        self.rows = rows
        logger.info(f"[previous] {len(self.lives)} live(s) carried ({self.linked} files "
                    f"linked, {len(rows)} indexed episodes); nothing is pushed into the "
                    f"prompt (the MFM carry: the model reads)")

    def audit(self) -> dict[str, Any]:
        return {"lives": len(self.lives), "sources": self.sources, "files_linked": self.linked}


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
