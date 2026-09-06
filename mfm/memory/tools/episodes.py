#!/usr/bin/env python3
"""Query the episode index the harness writes beside `logs.txt`.

Written into every MFM workspace as `./tools/episodes.py`; also importable as
`mfm.memory.tools.episodes` (the pure functions) by the harness. Standard library only,
because inside the sandbox nothing else is installed; `--sheet` needs PIL and says so
when it is missing.

    ./tools/episodes.py --last 5              the five most recent episodes
    ./tools/episodes.py --steps 4800 4900     episodes overlapping that step range
    ./tools/episodes.py --near 12.5 -30 [--radius 6]   episodes that started near (x, z)
    ./tools/episodes.py --tag stuck           episodes carrying a tag
    ./tools/episodes.py --grep "spruce_log"   episodes whose files mention the text
    ./tools/episodes.py ... --sheet out.png   tile the matching episodes' frames

Filters combine (AND). Each line: id, step range, tags, position, the action, the
outcome summary, the first harness note the entry ended with (why it stopped, what it
refused -- from `outcome.json`), and the directory holding `observation/image.png`,
`state/`, `action.json`, `outcome.json`.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
import os
import sys
from pathlib import Path
from typing import Any, Iterable


def read_index(root: Path, previous: bool = False) -> list[dict[str, Any]]:
    """`previous=True`: the merged index of the tasks finished before this one
    (`previous/index.jsonl`, written by the carry layer), whose paths already point
    under `previous/<task>/`."""
    path = Path(root) / ("previous" if previous else "") / "index.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def recent(rows: list[dict], k: int) -> list[dict]:
    return rows[-k:] if k > 0 else []


def steps(rows: list[dict], a: int, b: int) -> list[dict]:
    lo, hi = min(a, b), max(a, b)
    return [r for r in rows
            if r.get("first_step") is not None and r.get("last_step") is not None
            and r["first_step"] <= hi and r["last_step"] >= lo]


def near(rows: list[dict], x: float, z: float, radius: float = 6.0) -> list[dict]:
    out = []
    for r in rows:
        if r.get("x") is None or r.get("z") is None:
            continue
        if math.dist((float(r["x"]), float(r["z"])), (x, z)) <= radius:
            out.append(r)
    return out


def tagged(rows: list[dict], tag: str) -> list[dict]:
    return [r for r in rows if tag in (r.get("tags") or [])]


def same_observation(rows: list[dict], digest: str) -> list[dict]:
    """Episodes whose observation carried this hash (KiCad: the same screen seen before)."""
    return [r for r in rows if r.get("observation_hash") == digest]


def same_action(rows: list[dict], kind: str) -> list[dict]:
    return [r for r in rows if r.get("action_kind") == kind]


def grep(rows: list[dict], root: Path, text: str) -> list[dict]:
    needle = text.lower()
    out = []
    for r in rows:
        d = Path(root) / r.get("path", "")
        hay = [json.dumps(r)]
        for name in ("action.json", "outcome.json", "state/state.json"):
            p = d / name
            if p.exists():
                try:
                    hay.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
        if any(needle in h.lower() for h in hay):
            out.append(r)
    return out


def notes_of(root: Path | None, r: dict) -> list[str]:
    """The harness notes in the episode's `outcome.json` ([] when there are none)."""
    if root is None or not r.get("path"):
        return []
    p = Path(root) / r["path"] / "outcome.json"
    try:
        notes = json.loads(p.read_text(encoding="utf-8")).get("notes") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [str(n) for n in notes]


def first_note(root: Path | None, r: dict, limit: int = 220) -> str | None:
    """The first harness note in the episode's `outcome.json`, one line, or None.

    The index row's `summary` says what an entry changed; the note says why it ended
    (`no trunk detected`, `a SCREEN is open`, `refused: ...`). Listing rows without it
    told the model less than `tail logs.txt` did (lad2, 2026-09-05)."""
    notes = notes_of(root, r)
    if not notes:
        return None
    note = " ".join(notes[0].split())
    return note if len(note) <= limit else note[: limit - 3].rstrip() + "..."


def with_note(rows: Iterable[dict], root: Path | None) -> list[dict]:
    """Rows with a `note` key added (when the episode ended with one)."""
    out = []
    for r in rows:
        note = first_note(root, r)
        out.append({**r, "note": note} if note else dict(r))
    return out


def describe(r: dict) -> str:
    span = (f"steps {r['first_step']}-{r['last_step']}"
            if r.get("first_step") is not None and r.get("last_step") is not None
            else "steps ?")
    pos = (f" pos=({float(r['x']):.1f},{float(r['z']):.1f})"
           if r.get("x") is not None and r.get("z") is not None else "")
    tags = ",".join(r.get("tags") or []) or "-"
    note = f"  note: {r['note']}" if r.get("note") else ""
    seen = f"  saw: {r['perception']}" if r.get("perception") else ""
    effect = f"  effect: {r['effect']}" if r.get("effect") else ""
    return (f"{r['id']}  {span}  tags={tags}{pos}  action={r.get('action_kind') or '-'}  "
            f"{r.get('summary') or ''}{seen}{effect}{note}  -> {r.get('path')}/")


def contact_sheet(rows: Iterable[dict], root: Path, out: Path, cols: int = 4,
                  thumb: int = 320) -> Path:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("--sheet needs PIL, which this interpreter lacks") from exc
    rows = list(rows)
    if not rows:
        raise SystemExit("no episodes to tile")
    tiles = []
    for r in rows:
        img_path = Path(root) / r.get("image", "")
        try:
            im = Image.open(img_path).convert("RGB")
        except Exception:
            im = Image.new("RGB", (thumb, thumb // 2), (40, 40, 40))
        im.thumbnail((thumb, thumb))
        canvas = Image.new("RGB", (thumb, thumb + 16), (0, 0, 0))
        canvas.paste(im, (0, 0))
        ImageDraw.Draw(canvas).text((2, thumb + 2), f"{r['id']} s{r.get('first_step')}", fill=(255, 255, 255))
        tiles.append(canvas)
    n = len(tiles)
    rows_n = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows_n * (thumb + 16)), (0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * thumb, (i // cols) * (thumb + 16)))
    sheet.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="workspace holding index.jsonl and episodes/")
    ap.add_argument("--last", type=int)
    ap.add_argument("--steps", type=int, nargs=2, metavar=("A", "B"))
    ap.add_argument("--near", type=float, nargs=2, metavar=("X", "Z"))
    ap.add_argument("--radius", type=float, default=6.0)
    ap.add_argument("--tag")
    ap.add_argument("--action")
    ap.add_argument("--grep")
    ap.add_argument("--previous", action="store_true",
                    help="search the episodes of the tasks finished before this one")
    ap.add_argument("--same-screen", metavar="PNG",
                    help="episodes that faced exactly this screenshot (by content hash)")
    ap.add_argument("--sheet", help="write a contact sheet of the matching frames here")
    ap.add_argument("--json", action="store_true", help="one JSON object per line instead")
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows = read_index(root, previous=args.previous)
    if args.same_screen:
        try:
            digest = hashlib.sha256(Path(args.same_screen).read_bytes()).hexdigest()
        except OSError as e:
            print(f"cannot read {args.same_screen}: {e}", file=sys.stderr)
            return 2
        rows = same_observation(rows, digest)
    if args.steps:
        rows = steps(rows, *args.steps)
    if args.near:
        rows = near(rows, args.near[0], args.near[1], args.radius)
    if args.tag:
        rows = tagged(rows, args.tag)
    if args.action:
        rows = same_action(rows, args.action)
    if args.grep:
        rows = grep(rows, root, args.grep)
    if args.last is not None:
        rows = recent(rows, args.last)
    rows = with_note(rows, root)
    for r in rows:
        print(json.dumps(r) if args.json else describe(r))
    if not rows:
        print("(no matching episodes)", file=sys.stderr)
    if args.sheet:
        contact_sheet(rows, root, Path(args.sheet))
        print(f"sheet: {args.sheet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
