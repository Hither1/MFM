"""Retrieval over the episode index: the same functions the workspace CLI exposes
(`mfm/memory/tools/episodes.py`), importable by the harness, plus `recall_block` -- the
retrieval block a harness puts into the turn prompt when the `retrieval` flag is on.

The block exists because of what the lad2 diamond runs showed (2026-09-05): the model
read the last few sections every turn and each looked like a fresh small setback, so a
loop of twelve failed `harvest_tree` calls over 2,600 steps, or eight dark mining
entries in a row, was never seen as one thing. It queried the store in a quarter of its
turns and only ever asked for `--last N`. So the harness asks the three questions the
model did not, from the rows it already holds:

    streaks     which actions have changed nothing in their last N calls, and when the
                same action last did change something
    repeats     which harness note has ended the last N entries -- a loop whose entries
                do change something (each dark mining run banks cobblestone) but keep
                ending on the same diagnosis
    here        what happened at this spot before (earlier than the tail it can see)
    milestones  the entries that scored, as a recipe index

Everything here is derived from `index.jsonl` rows plus, for a few cited episodes, the
`notes` in their `outcome.json`; nothing is inferred and nothing is advice. The block
is the "what you did" the log already holds, put where the model is looking.
"""
from __future__ import annotations

import re
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from mfm.memory.tools.episodes import (  # noqa: F401
    describe, first_note, grep, near, notes_of, read_index, recent, same_action,
    same_observation, steps, tagged,
)

#: A row "changed something" when the entry scored or moved the inventory. Movement
#: alone does not count -- walking in a circle is the failure mode being surfaced --
#: except for the kinds the caller names in `movers`, whose point is to move: for
#: those, not being tagged `stuck` is the change.
CHANGE_TAGS = frozenset({"milestone", "inventory_changed"})


def changed(row: dict[str, Any], movers: Iterable[str] = (),
            openers: Iterable[str] = ()) -> bool:
    tags = set(row.get("tags") or [])
    if CHANGE_TAGS & tags:
        return True
    kind = row.get("action_kind")
    if kind in set(openers):
        # An entry whose job is to open a screen changed something iff one is open
        # at its end. lad4 (2026-09-05) pressed `use_until_gui` at a table that was
        # not there for 1,200 steps; as bookkeeping it was invisible.
        return "gui" in tags
    return kind in set(movers) and "stuck" not in tags


def ran(row: dict[str, Any]) -> bool:
    """False for an entry that never executed: it spans no ticks and changed nothing --
    a `craft` the parser deferred for want of planks, a procedure refused before it
    started. Those are the FAILING entry's fault, not this kind's, and counting them
    made the lad2 plank loop read as a `craft` streak when it was a `harvest_tree` one."""
    if changed(row):
        return True
    return (row.get("last_step") or 0) > (row.get("first_step") or 0)


def _spot(row: dict[str, Any]) -> tuple[int, int] | None:
    if row.get("x") is None or row.get("z") is None:
        return None
    return round(float(row["x"])), round(float(row["z"]))


def _note(root: Path | None, row: dict[str, Any], limit: int = 150) -> str | None:
    """The note that explains this row: the first one naming its action kind, else the
    first one. A note raised while the entry ran can be about the NEXT entry (the
    parser's "craft will expand when its turn comes..." lands in the open episode)."""
    notes = notes_of(root, row) if root is not None else []
    if not notes and row.get("note"):
        notes = [row["note"]]
    if not notes:
        return None
    kind = str(row.get("action_kind") or "")
    note = next((n for n in notes if kind and kind in str(n)), notes[0])
    note = " ".join(str(note).split())
    return note if len(note) <= limit else note[: limit - 3].rstrip() + "..."


def _split_summary(row: dict[str, Any]) -> tuple[str, str]:
    """(the entry as the log shows it, the outcome tail) from the row's summary:
    `dig_down(n=4) -> 44 ticks: moved 0.0, inv {...}` or, for a held raw action,
    `{"attack":1} x110: moved 0.0, milestone ['mine_log']`."""
    s = str(row.get("summary") or "")
    if s.startswith("[ACTION] "):
        s = s[len("[ACTION] "):]
    head, sep, tail = s.partition(" -> ")
    if sep:
        _, sep2, rest = tail.partition(": ")
        return head, (rest if sep2 else tail)
    head, sep, tail = s.partition(": moved ")
    return (head, "moved " + tail) if sep else (s, "")


def _action(row: dict[str, Any]) -> str:
    return _split_summary(row)[0]


def _outcome_tail(row: dict[str, Any]) -> str:
    return _split_summary(row)[1]


def streaks(rows: list[dict[str, Any]], *, min_len: int = 3,
            ignore: Iterable[str] = (), movers: Iterable[str] = (),
            openers: Iterable[str] = (), recent: int = 30) -> list[dict[str, Any]]:
    """Per action kind, the trailing run of episodes that changed nothing.

    Counted per kind, not per position in the log: the loop being surfaced is "this
    action has not worked in its last nine calls" while other entries in between (a
    craft, a pickup of dirt) did change something. Kinds in `ignore` are bookkeeping
    (look, equip, open/close a screen) whose "no change" is their normal outcome. A
    run whose last call is older than the `recent` most recent COUNTED rows -- the ones
    that could be part of a streak, so bookkeeping and never-ran entries do not age it
    -- is history, not a loop, and is not reported (three failed `stow_items` at step
    3094 are not news at step 6700). lad6b (2026-09-05): 39 rows of equip / open /
    deferred craft / close between two `harvest_tree` calls made an eight-call plank
    loop "stale" by the raw count, and its second refusal never came."""
    skip, movers, openers = set(ignore), set(movers), set(openers)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    counted = 0
    for r in rows:
        k = r.get("action_kind")
        if r.get("kind") != "episode" or not k or k in skip or not ran(r):
            continue
        by_kind.setdefault(k, []).append((counted, r))
        counted += 1
    stale_before = max(0, counted - recent) if recent > 0 else 0
    out = []
    for kind, irs in by_kind.items():
        if irs[-1][0] < stale_before:
            continue
        rs = [r for _, r in irs]
        n = 0
        while n < len(rs) and not changed(rs[-1 - n], movers, openers):
            n += 1
        if n < min_len:
            continue
        run = rs[-n:]
        success = next((r for r in reversed(rs[:-n]) if changed(r, movers, openers)), None)
        out.append({"kind": kind, "n": n, "since_step": run[0].get("first_step"),
                    "spots": len({s for s in map(_spot, run) if s is not None}),
                    "last": run[-1], "last_success": success, "rows": run})
    # The longest first; ties by recency of the run's last episode.
    out.sort(key=lambda s: (-s["n"], -(s["last"].get("last_step") or 0)))
    return out


_SENTENCE_MIN = 25


def _note_keys(note: str) -> dict[str, str]:
    """{key: sentence} for each sentence of the note long enough to be a diagnosis
    rather than a label; the key has digits stripped so `brightness 16/255` and
    `brightness 17/255` are one thing, and is lowercased."""
    out = {}
    for sent in re.split(r"(?<=[.!?])\s+", " ".join(note.split())):
        sent = sent.strip()
        if len(sent) < _SENTENCE_MIN:
            continue
        key = re.sub(r"\d+", "", sent).lower()
        out.setdefault(key, sent)
    return out


def repeated_note(rows: list[dict[str, Any]], root: Path | str | None, *, min_len: int = 3,
                  recent: int = 30, ignore: Iterable[str] = ()) -> dict[str, Any] | None:
    """The harness note (one sentence of it) that ended the most recent entries, when
    it ended at least `min_len` of them in a row. Only rows carrying a note take part;
    entries without one (a look, an equip) neither extend nor break the chain, and
    `ignore` kinds are skipped as in `streaks`. Reads the last `recent` rows' notes."""
    if root is None:
        return None
    skip = set(ignore)
    tail = [r for r in rows[-recent:] if r.get("kind") == "episode"
            and r.get("action_kind") not in skip]
    noted: list[tuple[dict[str, Any], dict[str, str]]] = []
    for r in reversed(tail):
        keys: dict[str, str] = {}
        for n in notes_of(Path(root), r):
            keys.update(_note_keys(n))
        if keys:
            noted.append((r, keys))
    if len(noted) < min_len:
        return None
    best: dict[str, Any] | None = None
    for key, sent in noted[0][1].items():
        n = 0
        while n < len(noted) and key in noted[n][1]:
            n += 1
        if n >= min_len and (best is None or n > best["n"]):
            run = [r for r, _ in noted[:n]]
            best = {"n": n, "sentence": sent, "since_step": run[-1].get("first_step"),
                    "last": run[0], "kinds": dict(Counter(str(r.get("action_kind")) for r in run))}
    return best


def streak_line(s: dict[str, Any], root: Path | str | None = None,
                pos: dict | tuple | None = None) -> str:
    """One streak as a sentence: the run, the note it last ended on, the last time
    the same action changed something -- and where, with the distance from `pos`,
    because "it worked at step 17" is a fact and "it worked 14 blocks north-west of
    here" is somewhere to go (lad6b, 2026-09-05: refused `harvest_tree` eight calls
    into the plank loop, overrode with "a trunk is directly ahead", and it was not).
    Used by the recall block and, under the refusal flag, as the reason an entry of
    that kind is refused."""
    root = Path(root) if root is not None else None
    last = s["last"]
    line = (f"`{s['kind']}` changed nothing in its last {s['n']} calls "
            f"(since step {s['since_step']}, {s['spots']} spot"
            f"{'s' if s['spots'] != 1 else ''}; latest {last['id']}, "
            f"steps {last.get('first_step')}-{last.get('last_step')})")
    note = _note(root, last)
    if note:
        line += f': "{note}"'
    ok = s["last_success"]
    if ok is not None:
        line += (f". It last changed something at step {ok.get('first_step')} "
                 f"({ok['id']}: {_action(ok)}){_where(ok, pos)}.")
    else:
        line += ". It has never changed anything."
    return line


def override_of(root: Path | str | None, row: dict[str, Any]) -> str | None:
    """The `why` the agent put on this episode's entry to run it past a refusal, from
    its action.json; None when there was none (or the file is not there)."""
    if root is None or not row.get("path"):
        return None
    try:
        a = json.loads((Path(root) / row["path"] / "action.json").read_text())
    except (OSError, ValueError):
        return None
    entry = a.get("entry") if isinstance(a.get("entry"), dict) else a
    why = entry.get("why")
    return str(why) if why else None


def burned_override(root: Path | str | None, run: list[dict[str, Any]]) -> tuple[dict, str] | None:
    """The most recent episode in a streak's run that the agent ran past a refusal
    with a `why`, and what it said -- it ran, and changed nothing, so the claim is
    spent (lad6b, 2026-09-05: "a spruce trunk is directly ahead", 300 ticks, none)."""
    for r in reversed(run):
        why = override_of(root, r)
        if why:
            return r, why
    return None


def _where(row: dict[str, Any], pos: dict | tuple | None) -> str:
    """" at (x, y, z), N blocks E and M blocks S of here" for a row with a position."""
    if row.get("x") is None or row.get("z") is None:
        return ""
    x, z = float(row["x"]), float(row["z"])
    y = row.get("y")
    at = f" at ({x:.0f}, {float(y):.0f}, {z:.0f})" if y is not None else f" at (x {x:.0f}, z {z:.0f})"
    if pos is None:
        return at
    if isinstance(pos, dict):
        px, pz = pos.get("x"), pos.get("z")
    else:
        px, pz = pos[0], pos[-1]
    if px is None or pz is None:
        return at
    dx, dz = x - float(px), z - float(pz)
    dist = (dx * dx + dz * dz) ** 0.5
    if dist < 1.5:
        return at + ", where you stand"
    parts = []
    if abs(dx) >= 1:
        parts.append(f"{abs(dx):.0f} {'east' if dx > 0 else 'west'}")
    if abs(dz) >= 1:
        parts.append(f"{abs(dz):.0f} {'south' if dz > 0 else 'north'}")
    return at + f", {dist:.0f} blocks from here ({' and '.join(parts)})"


def here_before(rows: list[dict[str, Any]], pos: tuple[float, float] | None, *,
                radius: float = 6.0, exclude_last: int = 6) -> list[dict[str, Any]]:
    """Episodes that started within `radius` of `pos`, older than the `exclude_last`
    most recent rows -- the tail the model reads anyway is not recalled to it."""
    if pos is None:
        return []
    older = rows[:-exclude_last] if exclude_last > 0 else rows
    return [r for r in near(older, pos[0], pos[1], radius) if r.get("kind") == "episode"]


def left_behind(rows: list[dict[str, Any]], root: Path | str | None, *,
                items: Iterable[str] = ("crafting_table", "furnace")) -> list[dict[str, Any]]:
    """Placed blocks the agent walked away from: for each item, the episodes whose
    `inventory_delta` lost one (a placement, at that episode's position) that no later
    episode gained one back without crafting it (a pickup). Newest last.

    lad3 (2026-09-05): the table was placed at step 571 at Y=68 and left there; at
    step 7117, at Y=12 with every ingredient of the iron pickaxe, the climb back took
    4,800 steps. The contract's rule ("carry ONE table") was 400 lines from the
    decision; this is the fact, from the record, at the decision."""
    if root is None:
        return []
    root = Path(root)
    items = tuple(items)
    open_: dict[str, list[dict[str, Any]]] = {i: [] for i in items}
    for r in rows:
        s = str(r.get("summary") or "")
        if not any(i in s for i in items):
            continue
        try:
            oc = json.loads((root / r["path"] / "outcome.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        delta = oc.get("inventory_delta") or {}
        events = " ".join(oc.get("events") or [])
        for item in items:
            d = delta.get(item, 0)
            if d < 0:
                open_[item].append({"item": item, "id": r["id"], "step": r.get("first_step"),
                                    "x": r.get("x"), "y": r.get("y"), "z": r.get("z")})
            elif d > 0 and f"craft_item {item}" not in events and open_[item]:
                open_[item].pop()          # picked back up
    out = [p for item in items for p in open_[item]]
    out.sort(key=lambda p: p["step"] or 0)
    return out


def milestone_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if "milestone" in (r.get("tags") or [])]


def recall_block(rows: list[dict[str, Any]], root: Path | str | None = None, *,
                 pos: tuple[float, float] | None = None, radius: float = 6.0,
                 streak_min: int = 3, ignore_kinds: Iterable[str] = (),
                 movers: Iterable[str] = (), openers: Iterable[str] = (),
                 exclude_last: int = 6, streak_recent: int = 30, repeat_min: int = 3,
                 max_streaks: int = 3, max_here: int = 3, max_milestones: int = 10) -> str:
    """The retrieval block for one turn, or "" when there is nothing to say.

    Three parts, each present only when it has content; every line names the episode
    ids it is computed from so the model can open them (`./tools/episodes.py --steps`,
    or the directory directly)."""
    root = Path(root) if root is not None else None
    lines: list[str] = []

    movers, openers = set(movers), set(openers)
    for s in streaks(rows, min_len=streak_min, ignore=ignore_kinds,
                     movers=movers, openers=openers, recent=streak_recent)[:max_streaks]:
        lines.append("- " + streak_line(s, root, pos))

    rep = repeated_note(rows, root, min_len=repeat_min, recent=streak_recent,
                        ignore=ignore_kinds)
    if rep is not None:
        kinds = ", ".join(f"{k} x{n}" for k, n in
                          sorted(rep["kinds"].items(), key=lambda kv: (-kv[1], kv[0])))
        sent = rep["sentence"]
        if len(sent) > 160:
            sent = sent[:157].rstrip() + "..."
        lines.append(f"- The same harness note ended the last {rep['n']} entries that "
                     f"carried one (since step {rep['since_step']}; {kinds}): \"{sent}\"")

    here = here_before(rows, pos, radius=radius, exclude_last=exclude_last)
    if here:
        kinds = Counter(str(r.get("action_kind")) for r in here)
        did = [r for r in here if changed(r, movers, openers)]
        stuck = [r for r in here if "stuck" in (r.get("tags") or [])]
        first_step = min(r.get("first_step") or 0 for r in here)
        last_step = max(r.get("last_step") or 0 for r in here)
        kinds_txt = ", ".join(f"{k} x{n}" for k, n in kinds.most_common(6))
        line = (f"- Here before (within {radius:g} blocks): {len(here)} episode"
                f"{'s' if len(here) != 1 else ''}, steps {first_step}-{last_step}: "
                f"{kinds_txt}; {len(did)} changed something, {len(stuck)} stuck.")
        cite = did[-max_here:] if did else stuck[-max_here:]
        for r in cite:
            line += (f"\n    {r['id']} step {r.get('first_step')}: {_action(r)} -> "
                     f"{_outcome_tail(r) or 'no change'}")
        lines.append(line)

    ms = milestone_rows(rows)
    if ms:
        shown = ms[-max_milestones:]
        items = [f"{_milestone_name(r)} step {r.get('first_step')} "
                 f"({r['id']}: {_action(r)})" for r in shown]
        lines.append("- Milestones so far, with the entry that scored each: "
                     + "; ".join(items) + ".")

    if not lines:
        return ""
    return ("[RECALL] computed from episodes/ by the harness -- what you did, not "
            "advice:\n" + "\n".join(lines))


def _milestone_name(row: dict[str, Any]) -> str:
    s = str(row.get("summary") or "")
    _, sep, tail = s.partition("milestone ")
    if not sep:
        return "milestone"
    return tail.strip("[]'\" ").replace("', '", "+")
