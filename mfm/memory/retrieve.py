"""Retrieval over the episode index: the same functions the workspace CLI exposes
(`mfm/memory/tools/episodes.py`), importable by the harness, plus `recall_block` -- the
retrieval block a harness puts into the turn prompt when the `retrieval` flag is on.

The block exists because of what the diamond runs showed: the model
read the last few sections every turn and each looked like a fresh small setback, so a
loop of twelve failed `harvest_tree` calls over 2,600 steps, or eight dark mining
entries in a row, was never seen as one thing. It queried the store in a quarter of its
turns and only ever asked for `--last N`. So the harness asks the three questions the
model did not, from the rows it already holds:

    plan repeat the same [PLAN]/EXPECT re-issued turn after turn with nothing moving --
                the plan-grain stall an atom-grain streak cannot see (several runs,
                the same EXPECT ran turn after turn while the only thing the
                block had to say was that `hotbar.6` had changed nothing)
    streaks     which actions have changed nothing in their last N calls, and when the
                same action last did change something
    repeats     which harness note has ended the last N entries -- a loop whose entries
                do change something (each dark mining run banks cobblestone) but keep
                ending on the same diagnosis
    here        what happened at this spot before (earlier than the tail it can see)
    milestones  the entries that scored, as a recipe index

Everything here is derived from `index.jsonl` rows plus, for a few cited episodes, the
`notes` in their `outcome.json` and the turn/plan text in their `action.json`; nothing
is inferred and nothing is advice. The block
is the "what you did" the log already holds, put where the model is looking.
"""
from __future__ import annotations

import re
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from mfm.memory.tools.episodes import (  # noqa: F401
    describe, events_of, first_note, grep, near, notes_of, read_index, same_action,
    same_observation, steps, tagged,
)

#: A row "changed something" when the entry scored or moved the inventory. Movement
#: alone does not count -- walking in a circle is the failure mode being surfaced --
#: except for the kinds the caller names in `movers`, whose point is to move: for
#: those, not being tagged `stuck` is the change.
#: `broke`: the MCU adapter's tag for a block-breaking event (mine_block, craft_item,
#: pickup) -- an ore broken and not yet picked up changes no inventory, and one run
#: refused the `mine_ahead` that had just broken three iron ore as a
#: streak that "changed nothing".
CHANGE_TAGS = frozenset({"milestone", "inventory_changed", "broke"})


_MOVE_KEYS = frozenset({"forward", "back", "left", "right", "jump", "sneak", "sprint"})
RAW_NUDGE_TICKS = 8

#: A raw hotbar key (`hotbar.6`) and the procedure that presses one. Selecting a slot
#: is bookkeeping: it never moves the world, so a run of them is not a loop. One run
#: pressed `hotbar.6` 67 times and the block reported "`hotbar.6` changed
#: nothing in its last 61 calls" while the real stall was plan-grain. The caller's
#: `ignore` list lives in MCU (`mcu_worldmodel/episodes.py` RECALL_IGNORE_KINDS) and
#: cannot name `hotbar.N` without enumerating nine kinds, so the shape is excluded here.
_HOTBAR_RE = re.compile(r"^hotbar\.\d$")


def hotbar_only(kind: Any) -> bool:
    """True for a kind that is nothing but hotbar selection: `hotbar.6`,
    `equip_hotbar`, or a held key set composed only of those."""
    parts = [p for p in str(kind or "").split("+") if p]
    return bool(parts) and all(_HOTBAR_RE.match(p) or p == "equip_hotbar" for p in parts)


def raw_move(row: dict[str, Any]) -> bool:
    """A raw held-movement entry (`forward`, `forward+jump`, ...): its kind is the
    joined key set, nothing else."""
    parts = set(str(row.get("action_kind") or "").split("+"))
    return bool(parts) and parts <= _MOVE_KEYS


def moved_of(row: dict[str, Any]) -> float | None:
    m = re.search(r"moved (\d+(?:\.\d+)?)", str(row.get("summary") or ""))
    return float(m.group(1)) if m else None


def raw_nudge(row: dict[str, Any]) -> bool:
    """A raw movement shorter than RAW_NUDGE_TICKS: a one-tick `forward` to square up
    before a dig. One run's RECALL read "forward changed nothing in its last 34 calls ...
    never changed anything" while the avatar walked fine: every nudge moved 0.1 and
    counted as a failure. Nudges are not in the streak
    statistic at all."""
    return raw_move(row) and ((row.get("last_step") or 0) - (row.get("first_step") or 0)) < RAW_NUDGE_TICKS


def changed(row: dict[str, Any], movers: Iterable[str] = (),
            openers: Iterable[str] = ()) -> bool:
    tags = set(row.get("tags") or [])
    if CHANGE_TAGS & tags:
        return True
    kind = row.get("action_kind")
    if raw_move(row):
        # A held walk changed something iff it moved: the summary's `moved` is the fact.
        mv = moved_of(row)
        return mv is not None and mv >= 0.5 and "stuck" not in tags
    if kind in set(openers):
        # An entry whose job is to open a screen changed something iff one is open
        # at its end. One run pressed `use_until_gui` at a table that was
        # not there for 1,200 steps; as bookkeeping it was invisible.
        return "gui" in tags
    return kind in set(movers) and "stuck" not in tags


def ran(row: dict[str, Any]) -> bool:
    """False for an entry that never executed: it spans no ticks and changed nothing --
    a `craft` the parser deferred for want of planks, a procedure refused before it
    started. Those are the FAILING entry's fault, not this kind's, and counting them
    made the plank loop read as a `craft` streak when it was a `harvest_tree` one."""
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
    run whose last call is older than the `recent` most recent rows is history, not a
    loop, and is not reported (three failed `stow_items` at step 3094 are not news at
    step 6700). Hotbar selection (`hotbar_only`) is excluded whatever the caller's
    `ignore` says: pressing a slot key changes nothing by design."""
    skip, movers, openers = set(ignore), set(movers), set(openers)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    counted = 0
    for r in rows:
        k = r.get("action_kind")
        if (r.get("kind") != "episode" or not k or k in skip or hotbar_only(k)
                or not ran(r) or raw_nudge(r)):
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
    here" is somewhere to go (one run: refused `harvest_tree` eight calls
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
    if _frame(last):
        line += f" Frame: {_frame(last)}"
    return line


def _frame(row: dict[str, Any]) -> str:
    """The frame path of a row (the index's `image`, else the conventional path). A row
    that carries `image: None` was written by a store that kept no frame for it (an
    encode failure): no path, rather than the conventional one to a file that is not
    there."""
    img = row.get("image")
    if img:
        return str(img)
    if "image" in row:
        return ""
    rid = row.get("id")
    return f"episodes/{rid}/observation/image.png" if rid else ""


def bearing(pos: tuple[float, float] | None, row: dict[str, Any]) -> str:
    """Where a cited episode lies from `pos`: "4 blocks NE", "here" under a block.
    Minecraft axes: +x east, +z south. Several runs re-targeted a recalled place 0 times
    in 30 sampled turns: a citation without a direction is a fact, not a move."""
    try:
        x, z = float(row["x"]), float(row["z"])
    except (KeyError, TypeError, ValueError):
        return ""
    if pos is None:
        return ""
    dx, dz = x - pos[0], z - pos[1]
    d = (dx * dx + dz * dz) ** 0.5
    if d < 1.0:
        return "here"
    ang = (math.degrees(math.atan2(dx, -dz)) + 360.0) % 360.0     # 0 = north (-z)
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return f"{d:.0f} blocks {names[int((ang + 22.5) // 45) % 8]}"


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

    One run: the table was placed at step 571 at Y=68 and left there; at
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


def uncollected(rows: list[dict[str, Any]], root: Path | str | None,
                drops: dict[str, str], *, recent: int = 12) -> list[dict[str, Any]]:
    """Blocks broken in the last `recent` episodes whose drops were never picked up:
    [{item, broke, picked, row}] with the episode that broke them. `drops` maps the
    block to what it drops ({"iron_ore": "iron_ore", "coal_ore": "coal"}); from the
    adapter's events ("mine_block X +n", "pickup Y +n"). One run
    broke five iron ore and picked up none -- the drops lay in the dark cavity while
    every later aim swung at the empty hole; two runs did the same with one."""
    if root is None:
        return []
    root = Path(root)
    eps = [r for r in rows if r.get("kind") == "episode"][-recent:]
    broke: dict[str, tuple[int, dict]] = {}
    picked: dict[str, int] = {}
    for r in eps:
        for e in events_of(root, r):
            parts = e.split()
            if len(parts) < 2:
                continue
            try:
                n = int(parts[2].lstrip("+")) if len(parts) > 2 else 1
            except ValueError:
                n = 1
            if parts[0] == "mine_block" and parts[1] in drops:
                item = drops[parts[1]]
                prev = broke.get(item, (0, r))
                broke[item] = (prev[0] + n, r)
            elif parts[0] == "pickup" and parts[1] in drops.values():
                picked[parts[1]] = picked.get(parts[1], 0) + n
    out = []
    for item, (n, row) in broke.items():
        if n > picked.get(item, 0):
            out.append({"item": item, "broke": n, "picked": picked.get(item, 0), "row": row})
    return out


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
    spent (one run: "a spruce trunk is directly ahead", 300 ticks, none)."""
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


def milestone_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if "milestone" in (r.get("tags") or [])]


# -- plan grain ------------------------------------------------------------------
#
# The store already keeps what a plan-grain view needs, one level below the index: every
# episode's `action.json` carries the `turn` it belongs to, and the first entry of each
# turn also carries that turn's `briefing` and `plan` (the text after `[PLAN]`, EXPECT
# line included). One run's record: 2,256 action.json, all with a turn, 388 turns, all 388
# with a plan and an EXPECT line. Nothing is added to the index for this; `turns_of`
# reads the tail's action.json the way `repeated_note` reads the tail's outcome.json,
# which also means the six finished lives can be read with the same code.

PLAN_RECENT = 200

_EXPECT_RE = re.compile(r"^\s*EXPECT:\s*(.+?)\s*$", re.M)


def _action_json(root: Path | None, row: dict[str, Any]) -> dict[str, Any]:
    if root is None or not row.get("path"):
        return {}
    try:
        obj = json.loads((Path(root) / row["path"] / "action.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def expect_of(plan_text: str | None) -> str:
    """The `EXPECT:` line of a plan, or "" when the briefing had none."""
    m = _EXPECT_RE.search(str(plan_text or ""))
    return m.group(1).strip() if m else ""


def turns_of(rows: list[dict[str, Any]], root: Path | str | None = None, *,
             recent: int = PLAN_RECENT) -> list[dict[str, Any]]:
    """The last `recent` rows grouped into the model turns that issued them, oldest
    first. One record per turn:

        turn        the turn number (`agent.codex.calls`)
        expect      that turn's EXPECT line ("" when the briefing had none)
        plan        the plan text after `[PLAN]`, whitespace collapsed
        moved       blocks moved over the turn's entries (the summaries' `moved`)
        inventory   True when any entry scored or moved the inventory
        first_step / last_step / rows

    A row already carrying `turn`/`expect`/`plan` keys is used as it stands (a caller
    that stores them in the index, and the tests, need no disk); otherwise the fields
    come from the episode's `action.json`."""
    tail = rows[-recent:] if recent > 0 else list(rows)
    out: list[dict[str, Any]] = []
    by_turn: dict[Any, dict[str, Any]] = {}
    for r in tail:
        if r.get("kind") != "episode":
            continue
        a = r if "turn" in r else _action_json(root, r)
        t = a.get("turn")
        if t is None:
            continue
        rec = by_turn.get(t)
        if rec is None:
            rec = {"turn": t, "expect": "", "plan": "", "moved": 0.0, "inventory": False,
                   "first_step": r.get("first_step"), "last_step": r.get("last_step"),
                   "rows": []}
            by_turn[t] = rec
            out.append(rec)
        plan_text = str(a.get("plan") or "")
        expect = str(a.get("expect") or "") or expect_of(plan_text)
        if (plan_text or expect) and not (rec["plan"] or rec["expect"]):
            rec["plan"] = " ".join(plan_text.split())
            rec["expect"] = expect
        rec["moved"] += moved_of(r) or 0.0
        if CHANGE_TAGS & set(r.get("tags") or []):
            rec["inventory"] = True
        rec["last_step"] = r.get("last_step", rec["last_step"])
        rec["rows"].append(r)
    return out


def _plan_key(turn: dict[str, Any]) -> tuple[str, str]:
    """(normalised text, which field it came from) for a turn, ("", "") when neither
    the EXPECT line nor the plan text is there."""
    text = str(turn.get("expect") or "").strip()
    src = "EXPECT"
    if not text:
        text, src = str(turn.get("plan") or "").strip(), "PLAN"
    if not text:
        return "", ""
    return " ".join(text.split()).lower(), src


def plan_repeats(turns: list[dict[str, Any]], min_len: int = 3) -> dict[str, Any] | None:
    """The run of consecutive turns, ending at the latest one, that re-issued the same
    EXPECT line (or, without one, the same plan text) while nothing happened: the run's
    entries moved less than 0.5 blocks in total and none of them scored or moved the
    inventory. None when the run is shorter than `min_len`.

    A turn that moved, or that changed the inventory, ends the run at that point rather
    than disqualifying what came after it, so a stall that began after a successful turn
    is still reported -- and a repeat that IS getting somewhere is never reported.

    Pure: `turns` is what `turns_of` returns (or any list of such records)."""
    if not turns:
        return None
    key, src = _plan_key(turns[-1])
    if not key:
        return None
    run: list[dict[str, Any]] = []
    moved = 0.0
    for t in reversed(turns):
        if _plan_key(t)[0] != key or t.get("inventory"):
            break
        moved += float(t.get("moved") or 0.0)
        if moved >= 0.5:
            break
        run.append(t)
    if len(run) < min_len:
        return None
    run.reverse()
    last = run[-1]
    last_rows = last.get("rows") or []
    row = last_rows[-1] if last_rows else {}
    text = str(last.get("expect") if src == "EXPECT" else last.get("plan") or "")
    return {"n": len(run), "source": src, "text": " ".join(text.split()),
            "first_step": run[0].get("first_step"), "last_step": last.get("last_step"),
            "first_turn": run[0].get("turn"), "last_turn": last.get("turn"),
            "moved": round(moved, 2), "id": row.get("id"), "frame": _frame(row) if row else "",
            "turns": run}


_NUMS = re.compile(r"-?\d+(?:\.\d+)?")
#: A plan of this many entries that changed nothing is reported on its own (one run's
#: 21-entry plan at steps 24067-24188, moved 0.0; 43% of its entries sat in such plans).
LONG_PLAN = 12


def plan_stall(turns: list[dict[str, Any]], min_turns: int = 3,
               long_plan: int = LONG_PLAN) -> dict[str, Any] | None:
    """The run of latest consecutive turns in which NOTHING happened -- each moved less
    than 0.5 blocks and none scored or moved the inventory -- reported when it is
    `min_turns` long, or when the latest turn alone ran `long_plan` or more entries to
    no effect. Outcome-based, not text-based: the six full-task lives
    never re-issued an identical EXPECT three
    turns running, but 34-43% of their plan entries sat inside long plans that achieved
    nothing, and consecutive EXPECT lines were near-identical with the numbers changed.
    `same_text` says whether the run's EXPECT (or plan) lines are one text once numbers
    are stripped. None when there is nothing to say. Pure: `turns` is `turns_of`'s output."""
    if not turns:
        return None
    run: list[dict[str, Any]] = []
    moved = 0.0
    for t in reversed(turns):
        m = float(t.get("moved") or 0.0)
        if t.get("inventory") or m >= 0.5:
            break
        moved += m
        run.append(t)
    if not run:
        return None
    run.reverse()
    last = run[-1]
    entries = len(last.get("rows") or [])
    if len(run) < min_turns and entries < long_plan:
        return None
    keys = {" ".join(_NUMS.sub("#", str(t.get("expect") or t.get("plan") or "")).split()).lower()
            for t in run}
    last_rows = last.get("rows") or []
    row = last_rows[-1] if last_rows else {}
    text = str(last.get("expect") or last.get("plan") or "")
    return {"n": len(run), "entries": entries, "long_plan": entries >= long_plan,
            "same_text": len(run) > 1 and len(keys) == 1 and "" not in keys,
            "text": " ".join(text.split()), "first_step": run[0].get("first_step"),
            "last_step": last.get("last_step"), "first_turn": run[0].get("turn"),
            "last_turn": last.get("turn"), "moved": round(moved, 2), "id": row.get("id"),
            "frame": _frame(row) if row else "", "turns": run}


def plan_stall_line(run: dict[str, Any], root: Path | str | None = None,
                    limit: int = 120) -> str:
    """The stall as one sentence for the recall block: what did not happen, over how many
    turns and entries, and the EXPECT the model keeps writing."""
    text = run.get("text") or ""
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    if run["n"] == 1:
        line = (f"Your last plan ran {run['entries']} entries (steps {run['first_step']}-"
                f"{run['last_step']}) and changed nothing: moved={run['moved']:.1f}, no "
                f"inventory change")
    else:
        line = (f"Nothing happened for {run['n']} turns (turns {run['first_turn']}-"
                f"{run['last_turn']}, steps {run['first_step']}-{run['last_step']}): "
                f"moved={run['moved']:.1f}, no inventory change")
        if run.get("long_plan"):
            line += f"; the last plan ran {run['entries']} entries to no effect"
        if run.get("same_text"):
            line += ", the same EXPECT each time (numbers aside)"
    if text:
        line += f". Latest EXPECT: `{text}`"
    if run.get("frame"):
        line += f". Latest frame: {run['frame']}"
    return line


def plan_repeat_line(run: dict[str, Any], root: Path | str | None = None,
                     limit: int = 120) -> str:
    """The plan repeat as one sentence for the recall block. `root` is accepted for
    symmetry with `streak_line`; the frame path the line quotes is log-relative."""
    text = run.get("text") or ""
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    line = (f"The same {run['source']} {run['n']} turns running "
            f"(turns {run['first_turn']}-{run['last_turn']}, steps {run['first_step']}-"
            f"{run['last_step']}) with moved={run['moved']:.1f} and no inventory change: "
            f"`{text}`")
    if run.get("frame"):
        line += f". Latest frame: {run['frame']}"
    return line


def recall_block(rows: list[dict[str, Any]], root: Path | str | None = None, *,
                 pos: tuple[float, float] | None = None, radius: float = 6.0,
                 streak_min: int = 4, ignore_kinds: Iterable[str] = (),
                 movers: Iterable[str] = (), openers: Iterable[str] = (),
                 exclude_last: int = 6, streak_recent: int = 30, repeat_min: int = 3,
                 max_streaks: int = 2, max_here: int = 3, max_milestones: int = 0,
                 plan_repeat_min: int = 3, plan_recent: int = PLAN_RECENT) -> str:
    """The retrieval block for one turn, or "" when there is nothing to say.

    Parts, each present only when it has content; every line names the episode ids it is
    computed from so the model can open them (`./tools/episodes.py --steps`, or the
    directory directly). The plan repeat goes first when there is one: it is the largest
    unit of not-getting-anywhere the record can see, and the atom-grain lines under it
    are symptoms of it."""
    root = Path(root) if root is not None else None
    lines: list[str] = []

    stall = plan_stall(turns_of(rows, root, recent=plan_recent), min_turns=plan_repeat_min)
    if stall is not None:
        lines.append("- " + plan_stall_line(stall, root))

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
            where = bearing(pos, r)
            line += (f"\n    {r['id']} step {r.get('first_step')}"
                     + (f", {where}" if where else "") + f": {_action(r)} -> "
                     f"{_outcome_tail(r) or 'no change'}"
                     + (f" (frame: {_frame(r)})" if _frame(r) else ""))
        lines.append(line)

    # The milestone line is off by default: it repeated the ledger in
    # [STATE] every turn and was never acted on.
    ms = milestone_rows(rows) if max_milestones > 0 else []
    if ms:
        shown = ms[-max_milestones:]
        items = [f"{_milestone_name(r)} step {r.get('first_step')} "
                 f"({r['id']}: {_action(r)})" for r in shown]
        lines.append("- Milestones so far, with the entry that scored each: "
                     + "; ".join(items) + ".")

    if not lines:
        return ""
    return ("[RECALL] computed from episodes/ by the harness -- what you did, not "
            "advice:\n" + "\n".join(lines)
            + "\n  (one line not enough? `view_image` the cited frame: what that entry saw is "
              "what you will see there.)")


def _milestone_name(row: dict[str, Any]) -> str:
    s = str(row.get("summary") or "")
    _, sep, tail = s.partition("milestone ")
    if not sep:
        return "milestone"
    return tail.strip("[]'\" ").replace("', '", "+")
