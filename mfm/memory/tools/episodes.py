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
    ./tools/episodes.py --ores                every episode that mined or picked up ore
    ./tools/episodes.py --y-profile           how many game steps went into each y band
    ./tools/episodes.py ... --sheet out.png   tile the matching episodes' frames
    ./tools/episodes.py --then-now ep_000123 --q "is this the ledge I poured from?"
                                              that episode's frame beside the current
                                              view, as then_now.png (recognition check)
    ./tools/episodes.py ... --q "<question>"  say what the look is for (kept in the log)

Filters combine (AND). Each line: id, step range, tags, position, the action, the
outcome summary, the first harness note the entry ended with (why it stopped, what it
refused -- from `outcome.json`), and the directory holding `observation/image.png`,
`state/`, `action.json`, `outcome.json`.

`--ores` and `--y-profile` answer the two questions a search should ask its record:
"where have I seen ore, and at what y" and "where have I already looked". Both take
the same filters and both work with `--previous`. `--grep` searches the index rows
(action, summary, tags, the first harness note, the events); `--deep` opens every
episode's action/outcome/state files too, which is slow on a long record.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
import os
import re
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


def grep(rows: list[dict], root: Path, text: str, deep: bool = False) -> list[dict]:
    """Rows whose index line holds `text` (action, summary, tags, note, events, place).
    `deep` also reads each episode's action.json / outcome.json / state.json -- the plan
    text, every note, the inventory -- at a file open per episode. Rows written before
    the index carried `note` (no such key, `note` tag) get their notes read from
    outcome.json so an old life greps the same."""
    needle = text.lower()
    out = []
    for r in rows:
        hay = [json.dumps(r)]
        if deep:
            d = Path(root) / r.get("path", "")
            for name in ("action.json", "outcome.json", "state/state.json"):
                p = d / name
                if p.exists():
                    try:
                        hay.append(p.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        pass
        elif "note" not in r and "note" in (r.get("tags") or []):
            hay.extend(notes_of(root, r))
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


def events_of(root: Path | None, r: dict) -> list[str]:
    """The world events recorded in the episode's `outcome.json` -- the adapter's
    strings, e.g. MCU's "mine_block iron_ore +1" / "pickup iron_ore +1" ([] when none)."""
    if root is None or not r.get("path"):
        return []
    p = Path(root) / r["path"] / "outcome.json"
    try:
        events = json.loads(p.read_text(encoding="utf-8")).get("events") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [str(e) for e in events]


def first_note(root: Path | None, r: dict, limit: int = 220) -> str | None:
    if r.get("note"):
        note = " ".join(str(r["note"]).split())
        return note if len(note) <= limit else note[: limit - 3].rstrip() + "..."
    """The first harness note in the episode's `outcome.json`, one line, or None.

    The index row's `summary` says what an entry changed; the note says why it ended
    (`no trunk detected`, `a SCREEN is open`, `refused: ...`). Listing rows without it
    tells less than `tail logs.txt` does."""
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


#: The ore blocks worth remembering where they were. A name also counts with the
#: `deepslate_` prefix (`deepslate_redstone_ore`), which is the same vein deeper down.
ORES = frozenset({
    "ancient_debris", "coal_ore", "diamond_ore", "emerald_ore",
    "gold_ore", "iron_ore", "lapis_ore", "redstone_ore",
})
_ORE_EVENT_RE = re.compile(r"\b(mine_block|pickup|craft_item)\s+([a-z_]+)\s*\+(\d+)")


def is_ore(name: str) -> bool:
    n = str(name)
    return n in ORES or (n.startswith("deepslate_") and n[len("deepslate_"):] in ORES)


def ore_hits(root: Path | None, r: dict) -> list[str]:
    """What ore this episode mined or picked up, as `mine_block iron_ore +1` strings.

    Read from the episode's `outcome.json`: its `events` are the harness's own count of
    what broke and what entered the inventory, and `inventory_delta` catches an ore that
    arrived without an event line. `craft_item` is excluded -- a furnace output is not a
    place where ore was found."""
    if "events" in r:                       # a row that carries its outcome (the store;
        oc = {"events": r.get("events") or [],   # the carry enriches older lives' rows at seed time)
              "inventory_delta": r.get("inventory_delta") or {}}
    else:                                   # an older row: its outcome.json, one open per row
        if root is None or not r.get("path"):
            return []
        try:
            oc = json.loads((Path(root) / r["path"] / "outcome.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
    out, seen = [], set()
    for ev in oc.get("events") or []:
        m = _ORE_EVENT_RE.search(str(ev))
        if m and m.group(1) != "craft_item" and is_ore(m.group(2)):
            out.append(f"{m.group(1)} {m.group(2)} +{m.group(3)}")
            seen.add(m.group(2))
    for name, d in sorted((oc.get("inventory_delta") or {}).items()):
        if is_ore(name) and isinstance(d, (int, float)) and d > 0 and name not in seen:
            out.append(f"inventory {name} +{int(d)}")
    return out


def describe_ore(r: dict, hits: list[str]) -> str:
    pos = (f"({float(r['x']):.0f},{float(r['y']):.0f},{float(r['z']):.0f})"
           if all(r.get(k) is not None for k in "xyz") else "(?)")
    life = f"  life {r['life']}" if r.get("life") is not None else ""
    # A row whose `image` is explicitly None comes from a record that keeps no frames
    # (the "without historical images" ablation): point at the episode, not at a file
    # that is not there. A row without the key is an older life: the conventional path.
    frame = (r.get("image") or (f"{r.get('path')}/" if "image" in r
                                 else f"{r.get('path')}/observation/image.png"))
    return (f"{r['id']}  step {r.get('first_step')}  y={_fmt_y(r)}  pos={pos}{life}  "
            f"{', '.join(hits)}  -> {frame}")


def _fmt_y(r: dict) -> str:
    return f"{float(r['y']):.0f}" if r.get("y") is not None else "?"


def ore_rows(rows: Iterable[dict], root: Path | None) -> list[tuple[dict, list[str]]]:
    """(row, hits) for every episode whose outcome names an ore, oldest first."""
    out = []
    for r in rows:
        hits = ore_hits(root, r)
        if hits:
            out.append((r, hits))
    return out


def y_profile(rows: Iterable[dict], band: int = 4) -> dict[int, int]:
    """{band floor: game steps} -- how long the agent spent in each `band`-block slice
    of y. An episode's span (`last_step - first_step`) is credited to the band of the y
    it started at, so this is "where have I already looked", in the units the log counts
    in. Episodes without a y, and the zero-length ones, contribute nothing."""
    out: dict[int, int] = {}
    for r in rows:
        if r.get("y") is None:
            continue
        span = (r.get("last_step") or 0) - (r.get("first_step") or 0)
        if span <= 0:
            continue
        floor = int(math.floor(float(r["y"]) / band) * band)
        out[floor] = out.get(floor, 0) + span
    return out


def print_y_profile(rows: list[dict], band: int = 4, width: int = 40) -> None:
    """The profile as a bar chart, deepest band last; one block per life when the rows
    carry a `life` (that is, under `--previous`)."""
    groups: dict[Any, list[dict]] = {}
    for r in rows:
        groups.setdefault(r.get("life"), []).append(r)
    for life in sorted(groups, key=lambda v: (v is None, v)):
        prof = y_profile(groups[life], band)
        label = "this life" if life is None else f"life {life}"
        total = sum(prof.values())
        print(f"[{label}] {total} steps over {len(prof)} y bands of {band}")
        if not prof:
            continue
        top = max(prof.values())
        for floor in sorted(prof, reverse=True):
            n = prof[floor]
            bar = "#" * max(1, round(width * n / top))
            print(f"  y {floor:>4}..{floor + band - 1:<4} {n:>7} steps  {bar}")


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


def then_now(root: Path, then: str, now: str | None, out: Path,
             rows: list[dict] | None = None) -> tuple[Path, str]:
    """Write the remembered frame (`then`: an episode id or a frame path) beside the
    current view (`now`: a path; default the attached frame the harness keeps at
    ../attach/frame.png) as one image with labels. Returns (out, caption).

    The check VISTA's inspect makes side by side: is the place in front of me the
    place the record describes? A walk by coordinate that never compares digs the
    wrong place with confidence."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("--then-now needs PIL, which this interpreter lacks") from exc
    root = Path(root)
    rows = rows if rows is not None else read_index(root) + read_index(root, previous=True)
    row = next((r for r in rows if r.get("id") == then), None)
    if row is not None:
        then_path = root / str(row.get("image") or f"{row.get('path')}/observation/image.png")
        label = (f"THEN {row['id']} step {row.get('first_step')}"
                 + (f" at ({float(row['x']):.0f},{float(row['z']):.0f})"
                    if row.get("x") is not None and row.get("z") is not None else ""))
    else:
        then_path = Path(then) if Path(then).is_absolute() else root / then
        if then_path.is_dir():                      # an episode directory (this life's or previous/life_i/...)
            then_path = then_path / "observation" / "image.png"
        label = f"THEN {then}"
    if not then_path.exists():
        raise SystemExit(f"no frame for {then!r}: not an episode id in the index and not a file")
    now_path = Path(now) if now else (root.resolve().parent / "attach" / "frame.png")
    if not now_path.exists():
        raise SystemExit(f"no current view at {now_path}; pass --now <png>")
    a = Image.open(then_path).convert("RGB")
    b = Image.open(now_path).convert("RGB")
    h = 360
    a = a.resize((max(1, round(a.width * h / a.height)), h))
    b = b.resize((max(1, round(b.width * h / b.height)), h))
    canvas = Image.new("RGB", (a.width + b.width + 8, h + 18), (0, 0, 0))
    canvas.paste(a, (0, 18)); canvas.paste(b, (a.width + 8, 18))
    d = ImageDraw.Draw(canvas)
    d.text((2, 2), label, fill=(255, 255, 0))
    d.text((a.width + 10, 2), "NOW (the attached view)", fill=(255, 255, 0))
    out = Path(out)
    canvas.save(out)
    return out, label


def frameless(rows: list[dict]) -> bool:
    """True when the record keeps no frames: every row carries `image: None` (the
    store writes the key on every row; a record with images has paths there). An
    empty record, or one whose rows predate the key, is not frameless."""
    rows = [r for r in rows if r.get("kind") != "initial"] or list(rows)
    return bool(rows) and all("image" in r and r.get("image") is None for r in rows)


NO_FRAMES = ("this run keeps no frames in its record (episodes/ holds state, action and "
             "outcome only; the current view is the image attached to your turn): "
             "--sheet and --then-now have nothing to show")


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
    ap.add_argument("--deep", action="store_true",
                    help="with --grep: also search every episode's action/outcome/state files (slow on a long record)")
    ap.add_argument("--previous", action="store_true",
                    help="search the episodes of the tasks finished before this one")
    ap.add_argument("--ores", action="store_true",
                    help="only the episodes that mined or picked up ore, with where and at what y")
    ap.add_argument("--y-profile", action="store_true",
                    help="game steps spent per y band instead of the episode lines "
                         "(where you have already looked)")
    ap.add_argument("--band", type=int, default=4, help="y band height for --y-profile")
    ap.add_argument("--same-screen", metavar="PNG",
                    help="episodes that faced exactly this screenshot (by content hash)")
    ap.add_argument("--sheet", help="write a contact sheet of the matching frames here")
    ap.add_argument("--json", action="store_true", help="one JSON object per line instead")
    ap.add_argument("--then-now", metavar="EP_OR_PNG",
                    help="write that episode's frame beside the current view (then_now.png)")
    ap.add_argument("--now", metavar="PNG", help="the current view for --then-now "
                    "(default: the attached frame, ../attach/frame.png)")
    ap.add_argument("--out", default="then_now.png", help="output of --then-now")
    ap.add_argument("--q", metavar="QUESTION",
                    help="what this look is meant to answer; printed back so the record keeps it")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if (args.then_now or args.sheet) and frameless(read_index(root) + read_index(root, previous=True)):
        raise SystemExit(NO_FRAMES)
    if args.then_now:
        out, label = then_now(root, args.then_now, args.now, Path(args.out))
        q = args.q or "(no --q given: what question does this look answer?)"
        # The image tool's name depends on the CLI running this shell: codex's view_image,
        # or Read under Claude Code (the harness sets MFM_IMAGE_TOOL for that channel).
        print(f"wrote {out}: {label} | NOW. Q: {q}. View it with "
              f"{os.environ.get('MFM_IMAGE_TOOL', 'view_image')}.")
        return 0
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
        rows = grep(rows, root, args.grep, deep=args.deep)
    if args.last is not None:
        rows = recent(rows, args.last)
    if args.y_profile:
        if not rows:
            print("(no matching episodes)", file=sys.stderr)
        print_y_profile(rows, max(1, args.band))
        if args.q:
            print(f"Q: {args.q}", file=sys.stderr)
        return 0
    if args.ores:
        hits = ore_rows(rows, root)
        for r, what in hits:
            print(json.dumps({**r, "ore": what}) if args.json else describe_ore(r, what))
        if not hits:
            print("(no episode in this selection touched ore)", file=sys.stderr)
        if args.sheet and hits:
            contact_sheet([r for r, _ in hits], root, Path(args.sheet))
            print(f"sheet: {args.sheet}", file=sys.stderr)
        if args.q:
            print(f"Q: {args.q}", file=sys.stderr)
        return 0
    rows = with_note(rows, root)
    for r in rows:
        print(json.dumps(r) if args.json else describe(r))
    if not rows:
        print("(no matching episodes)", file=sys.stderr)
    if args.sheet:
        contact_sheet(rows, root, Path(args.sheet))
        print(f"sheet: {args.sheet}" + (f"  Q: {args.q}" if args.q else ""), file=sys.stderr)
    elif args.q:
        print(f"Q: {args.q}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
