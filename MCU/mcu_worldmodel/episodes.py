"""The MFM arm's adapter: mfm's episode store, driven from the chassis's own hook points.

`--memory mfm` is the logbook arm (same chassis, one append-only `logs.txt`) plus the
Multimodal Filesystem Memory beside it: `episodes/ep_NNNNNN/` one per plan entry,
`index.jsonl`, and `tools/episodes.py` to query them. Everything under `episodes/` is
written by `mfm.memory.store.EpisodeStore`, which knows only the layout; what is
Minecraft about the contents is defined here, and the chassis calls in at four moments:

    initial      `WorldModelAgent.start`        ep_000000, the initial state
    open         an entry's first tick is popped  observation image + state, action.json
    observe      every `observe` tick             the entry's running state (for outcome.json)
    close_entry  `_log_entry_done`                outcome.json, one index row

An episode is one plan entry -- a procedure call (`dig_down(n=4) -> 44 ticks`) or a
raw held action -- which is the unit `_log_entry_done` writes one log section for, so
the store's rows and the log's sections are the same history twice. The store's own
`MemoryAgent` hooks are implemented on this object (it is the "agent" the store sees),
so `mfm.memory` itself is untouched.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from loguru import logger

from mfm.agent.base import Observation
from mfm.memory.retrieve import (burned_override, left_behind, notes_of, recall_block,
                                 streak_line, streaks, uncollected)
from mfm.memory.store import EpisodeStore

from mcu_worldmodel.actions import describe_entry
from mcu_worldmodel.milestones import inventory_counts, location
from mcu_worldmodel.previous import PreviousLives

#: Counted in the rollouts: how often the model ran the query tool.
ROLLOUT_EPISODES_TOOL = re.compile(r"tools/episodes\.py")

#: Procedures whose point is to move; an entry of one that moved under half a block
#: gets the `stuck` tag, the same rule the raw movement keys get. The registered
#: names (procedures.py) -- the first list had "goto" for `go_to`, so no go_to entry
#: was ever tagged stuck (lad1/lad2).
_MOVERS = frozenset({
    "go_to", "travel", "mine_forward", "strip_mine", "stair_down", "dig_down",
    "dig_up", "pillar_up", "walk", "explore", "swim_up", "climb", "descend", "tunnel",
    "run",
})
_MOVE_KEYS = frozenset({"forward", "back", "left", "right", "jump", "sprint"})

#: The paragraph the MFM arm adds to the logbook system prompt. Kept out of prompts.py
#: so the logbook arm's text does not move; `prompts._MFM_CONTRACT` splices it in.
#: `--expect`: the prediction protocol (VISTA's "state what you expect to see"), in
#: harness form: the EXPECT line is echoed next turn against the harness record.
MFM_EXPECT_NOTE = """\
**Expect, then compare.** End every briefing with one line `EXPECT: <what [STATE],
[INV] or [EVENT] will show if this plan works>`. The next turn opens with
`[EXPECTED]` (that line) and `[OBSERVED]` (what the harness recorded for the plan's
entries: moved, descended, inventory delta, events, the note it ended on). Begin the
briefing with `OBSERVED vs EXPECTED: ...` -- one sentence saying whether they match and
what differs -- before deciding anything. A plan whose expectation failed twice is not
re-proposed with the same target."""

#: `--frames`: the arm can read frames at pixel level.
MFM_FRAMES_NOTE = """\
**Frames.** `./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]` crops a region of a
frame (640x360 pixels) and magnifies it 4x for `view_image`.
Each turn's second image is a 2x2 sheet of the frames at this turn's events (LAVA
AHEAD, a hit, a stalled walk, a failed re-open, a water refusal). Before opening a
frame, write the question it answers in one clause ("is the lava in the next cell or
two cells off?", "what stopped the walk at that note?"). The [STATE]/[NOTE] lines say
WHERE and THAT; the frame says WHAT. One look costs one image -- when a plan's outcome
surprised you, look before you re-plan.
Frames are FILES: a script (numpy and PIL are available) can read many of them and
answer one question over the whole set -- where the orange was, which frames show a
screen -- faster than viewing them one by one; `./tools/episodes.py --near X Z` lists
them by place with their paths."""

MFM_MEMORY_NOTE = """\
`episodes/` holds the same history as `logs.txt` a second time, structured: one
directory per plan entry (one procedure call or one held raw action -- exactly the
entries the log has an "Action N" section for). In each `ep_NNNNNN/`:
`observation/image.png` (the view the entry started from), `state/state.json`
(position, inventory, hotbar, GUI, vitals, mobs, milestones at the entry's first
tick), `action.json` (the entry, its place in the
plan, the briefing and plan it came from) and `outcome.json` (what it changed: moved,
descended, inventory delta, [EVENT]s, milestone transition, harness notes, tags such as
`stuck`, `inventory_changed`, `milestone`, `damage`, `gui`, `flushed`). `index.jsonl`
has one line per episode. `./tools/episodes.py --last 5 | --steps A B | --near X Z
[--radius R] | --tag stuck | --action dig_down | --grep text` lists matching episodes
one per line with their paths; add `--sheet out.png` to tile their frames into one
image you can view, `--json` for the rows. These files persist across turns like
`logs.txt`; they are harness-written and immutable.

**Look back.** The frames are for looking, not only for listing. Before you walk to a
remembered place, view the frame of the episode that stood there (`./tools/episodes.py
--near X Z`, then `view_image episodes/<id>/observation/image.png`; or `./tools/episodes.py
--then-now <id> --q "<what this look answers>"`, which writes that frame beside the
current view as `then_now.png`) so you recognise it on arrival; after a hit, the frame of the episode tagged `damage` (what hit you is in
it); when a plan has failed twice for a reason the numbers do not give, tile
its last entries' frames (`--sheet out.png`) and look at them together; before a route
over ground you have not walked, the frames of the nearest episodes; before a place from
an earlier life, that life's frame of it (`--previous --near X Z`). The log knows where;
the frame knows what."""


#: Added to the contract when the retrieval flag is on (`--retrieval`): the turn
#: message then carries a block the harness computed from the store. Its content is
#: `mfm.memory.retrieve.recall_block`; this paragraph only says what the block is.
MFM_RETRIEVAL_NOTE = """\
When the episodes hold something that bears on this turn, the turn message carries a
`[RECALL]` block the harness computed from them: actions that have changed nothing in
their last several calls (and when the same action last did), what happened at this
spot earlier than the sections you can see. Each cited entry carries its frame path: when the one line is not enough,
`view_image` that frame -- what the entry saw is what you will see there -- or open the
episode (`./tools/episodes.py --steps A B`). Each cited place is given as a bearing and
a distance from where you stand. It is a reading of your own record, not advice, and it
is absent when there is nothing to recall."""

#: Added to the contract under the refusal flag (`--refuse`). The rules themselves
#: are `EpisodeBridge.refuse` and `descent_guard` below.
MFM_REFUSAL_NOTE = """\
Three proposals are refused before they spend steps, from the same record, and a
`why` that already ran and changed nothing is spent: the next `why` on that streak is
refused too, with the spent claim quoted. (1) An
entry whose action has changed nothing -- no event, no inventory change; for a
movement procedure, no movement; for one that opens a screen, no screen -- in its
last 5 calls ANYWHERE: the governor's rule, but across places and arguments, which
is how a loop looks from the record. (2) A `dig_down` or `stair_down` while your
crafting table stands placed 8 or more blocks above you and you carry none. (3) A
`dig_down` or `stair_down` below y 55 with no torch carried: mobs spawn only in the
dark and the ore watch is blind there. (4) The same descent with no sword carried: a
melee mob at arm's length in a 1-wide tunnel is what has killed every run that died,
and the runner fights it for you only with a sword in your hotbar. (5) Any plan that
does not go and collect ore you broke and never picked up (the record shows
`mine_block iron_ore` with no `pickup iron_ore` after it): the drop lies in the mined
cell, and three runs left theirs there and swung at the empty hole. A refusal drops the
whole plan for one no-op tick; its [NOTE] names the episodes it was computed from. To
run the entry anyway, say what is different: put `"why": "<one sentence>"` on the
entry, beside `args` (or `"leave_table": true` / `"unlit": true` / `"unarmed": true`
for a descent). The reason is recorded
in that episode's action.json, and each rule is refused at most twice in a row."""

#: The streak length that refuses (the recall block reports from 3); how many times
#: one streak may be refused before the entry is let through regardless (a refusal
#: costs a model turn, and a storm of them cost dmbr2 two calls a tick); how far
#: above the agent a placed table has to be before a descent without it is refused.
REFUSE_AT = 5
REFUSE_CAP = 2
LEFT_BEHIND_DY = 8
#: Below this y a descent without a torch is refused. lad5 (2026-09-05) died twice
#: to mobs in its own unlit shaft, at y 52 and y 27, with no torch either time;
#: lad2 spent 5,000 steps mining blind at y 12. The contract's "light BEFORE iron"
#: rule sits 40 lines from the descent checklist. 55, not 40: the first death was at y 52.
LIGHT_BELOW_Y = 55
_DESCENTS = frozenset({"dig_down", "stair_down"})
#: Event kinds that mean the world changed even when the inventory did not (the
#: drop is still on the floor): the episode is tagged `broke` and counts as a change.
_BROKE_EVENTS = frozenset({"mine_block", "craft_item", "pickup"})
#: Ore whose block, once broken, is a drop worth more than anything else in the plan:
#: the fifth rule refuses a plan that does not go and collect it. In this world the
#: ore block itself drops (the events say "pickup iron_ore").
_ORE_DROPS = {"iron_ore": "iron_ore", "deepslate_iron_ore": "iron_ore",
              "gold_ore": "gold_ore", "deepslate_gold_ore": "gold_ore",
              "coal_ore": "coal", "deepslate_coal_ore": "coal",
              "diamond_ore": "diamond", "deepslate_diamond_ore": "diamond"}
#: Entries that go somewhere or sweep the floor: a plan with one of these is
#: collecting, and is not refused by the fifth rule.
_COLLECTORS = frozenset({"collect_drops", "go_to", "travel", "walk", "explore",
                         "stair_down", "dig_down",
                         # and anything that fights or escapes: lad7a broke its ore
                         # seconds before a zombie reached it (the rule must not veto
                         # `attack` / `pillar_up` then)
                         "attack", "pillar_up", "fight", "face_entity", "place_block",
                         "eat", "sprint"})
#: Entries that break a block: a descent AFTER one of these in the same plan is read
#: as "collect the table, then go down" and is not refused -- lad4 (2026-09-05) was
#: refused twice for exactly that plan ("craft the iron pickaxe, recover the table,
#: then begin the descent") because the table was not yet carried at plan time.
_BREAKERS = frozenset({"mine_ahead", "mine_until", "chop", "chop_tree", "attack",
                       "collect_drops", "harvest_tree"})

#: Entry kinds whose normal outcome is "nothing changed": a streak of them is not a
#: loop. Everything else (harvest_tree, dig_down, craft, collect_drops, a held raw
#: key...) is meant to change the world or the inventory when it works.
RECALL_IGNORE_KINDS = frozenset({
    "look", "look_abs", "look_at", "equip_hotbar", "close_inventory",
    "inventory", "noop", "scan_around", "aim_at_ore", "aim_at_tree",
    "wait", "cursor_to", "cursor_to_cell", "cursor_to_slot",
}) | frozenset(f"hotbar.{i}" for i in range(1, 10))   # a raw slot press changes no world (of3r: "hotbar.6 ... 61 calls")
#: Entries whose job is to open a screen: they changed something iff a screen is
#: open at their end (the `gui` tag). Not bookkeeping: five `use_until_gui` that
#: opened nothing is the loop lad4 sat in.
_OPENERS = frozenset({"use_until_gui", "open_inventory", "place_and_open"})


def entry_kind(entry: dict[str, Any]) -> str:
    """The label an entry is tracked under: the procedure name, or the held keys."""
    if "procedure" in entry:
        return str(entry["procedure"])
    act = entry.get("action") or {}
    keys = [k for k, v in act.items() if v not in (0, [0, 0], [0.0, 0.0])]
    return "+".join(keys) or "noop"


def descent_guard(placements: list[dict[str, Any]], pos: dict | None,
                  inventory: dict[str, int], entries: list[dict[str, Any]],
                  placed_cells: dict[str, tuple] | None = None,
                  table_unopened: bool = False) -> str | None:
    """The left-behind rule as a pure function: the refusal text, or None.

    Refuses a descent while the most recent placed crafting table stands
    LEFT_BEHIND_DY or more blocks above the agent and none is carried, unless the
    entry says `leave_table`. Position and inventory are the present; the placement
    is the episode that lost the table (`left_behind`), which knows where the agent
    STOOD. The block's cell is the chassis's estimate (`placed_cells`, what
    `use_until_gui(item=...)` aims at); the note quotes that, as "about", and never
    the standing position as if it were the block -- lad4 (2026-09-05) was handed
    the standing position, took it for the exact cell, and pressed use at it for
    1,200 steps."""
    tables = [p for p in placements if p["item"] == "crafting_table" and p.get("y") is not None]
    if not tables or not pos or pos.get("y") is None:
        return None
    if int(inventory.get("crafting_table", 0) or 0) > 0:
        return None
    t = tables[-1]
    cell = (placed_cells or {}).get("crafting_table")
    if cell is not None and len(cell) == 3:
        t = {**t, "x": cell[0], "y": cell[1], "z": cell[2]}
        where_placed = (f"at about ({float(t['x']):.0f}, {float(t['y']):.0f}, "
                        f"{float(t['z']):.0f}) -- `use_until_gui(item=\"crafting_table\")` "
                        f"aims there for you")
    else:
        where_placed = (f"one block from where you stood, ({float(t['x']):.0f}, "
                        f"{float(t['y']):.0f}, {float(t['z']):.0f})")
    dy = float(t["y"]) - float(pos["y"])
    for i, e in enumerate(entries):
        k = entry_kind(e)
        if k not in _DESCENTS or e.get("leave_table"):
            continue
        if any(entry_kind(x) in _BREAKERS or "attack" in entry_kind(x).split("+")
               for x in entries[:i]):
            continue                      # the plan breaks something first: the pickup
        # The first `dig_down(until_y=12)` is proposed standing beside the table
        # (dy = 0): judge it by where it ends, not where it starts.
        target = (e.get("args") or {}).get("until_y")
        try:
            reach = max(dy, float(t["y"]) - float(target)) if target is not None else dy
        except (TypeError, ValueError):
            reach = dy
        if reach < LEFT_BEHIND_DY:
            continue
        where = (f"{dy:.0f} blocks ABOVE you" if dy >= LEFT_BEHIND_DY
                 else f"{reach:.0f} blocks above where this descent ends")
        if table_unopened:
            # lad5 (2026-09-05): refused, it spent 500 steps trying to reach a table its
            # own aimed open had already failed on. A table the record says cannot be
            # opened is one to replace, not to recover.
            fix = ("The record shows it could NOT be opened since it was placed (no screen "
                   "opened), so do not go back for it: craft a new one (4 planks = 1 log) "
                   "and carry it, or put `\"leave_table\": true` on the entry (beside "
                   "`args`) to descend without one.")
        else:
            fix = ("Mine it (one hit, it drops) and carry it, or put `\"leave_table\": "
                   "true` on the entry (beside `args`) to descend without it.")
        return (f"refused `{k}`: your crafting_table stands placed at step {t['step']} "
                f"({t['id']}) {where_placed}, {where}, and you carry none. "
                f"Everything you will craft down there (a furnace, the iron pickaxe) "
                f"needs a table. {fix}")
    return None


#: What the harness knows about a procedure's failure that its own note does not say.
#: Keyed by (kind, a substring of the note that ended the streak's last call).
_HINTS = {
    ("harvest_tree", "no trunk detected"):
        "Bark filling half the frame at arm's reach is too WIDE for the trunk detector "
        "(it wants a column), so \"a trunk is right there\" and \"no trunk detected\" "
        "are both true. Either `look_at` the bark block so the crosshair is ON it and "
        "`chop_tree(until_logs=1)` (~60 ticks by hand), or step back 3 blocks "
        "(`{\"back\": 1}` x15) so the trunk is a column and run `harvest_tree` again.",
    ("harvest_tree", "a SCREEN is open"):
        "Put `close_inventory()` FIRST in the plan, on its own line; the screen does not "
        "close by itself.",
}


def _last_note(root, s: dict) -> str:
    return " ".join(notes_of(root, s["last"]))


def hint_for(kind: str, note: str | None) -> str:
    """The hint for a streak of `kind` whose last call ended on `note`, or ""."""
    if not note:
        return ""
    for (k, sub), text in _HINTS.items():
        if k == kind and sub in note:
            return " " + text
    return ""


def _where_ok(s: dict, pos: dict | None) -> str:
    from mfm.memory.retrieve import _where
    ok = s.get("last_success")
    if ok is None:
        return "; it has never changed anything"
    return f"; it last changed something at step {ok.get('first_step')}{_where(ok, pos)}"


def light_guard(pos: dict | None, inventory: dict[str, int],
                entries: list[dict[str, Any]]) -> str | None:
    """The third rule as a pure function: a descent that ends (or starts) below
    LIGHT_BELOW_Y with no torch carried is refused, unless the entry says `unlit`."""
    if not pos or pos.get("y") is None:
        return None
    inv = {k: int(v or 0) for k, v in (inventory or {}).items()}
    if inv.get("torch", 0) > 0:
        return None
    y = float(pos["y"])
    for e in entries:
        k = entry_kind(e)
        if k not in _DESCENTS or e.get("unlit"):
            continue
        target = (e.get("args") or {}).get("until_y")
        try:
            low = min(y, float(target)) if target is not None else y
        except (TypeError, ValueError):
            low = y
        if low >= LIGHT_BELOW_Y:
            continue
        have = ", ".join(f"{n} x{inv[n]}" for n in ("coal", "charcoal", "stick", "spruce_log",
                                                     "oak_log", "birch_log", "spruce_planks",
                                                     "oak_planks", "birch_planks") if inv.get(n))
        return (f"refused `{k}`: it would take you to y {low:.0f} and you carry no torch. "
                f"Mobs spawn only in the dark (a previous run died twice in its own unlit "
                f"shaft) and the ore watch cannot see ore in it. 1 coal + 1 stick = 4 torches "
                f"in the 2x2 grid (charcoal from a log in the furnace does the same); you "
                f"carry {have or 'none of coal, sticks, logs or planks -- get a log first'}. "
                f"Craft them, or put `\"unlit\": true` on the entry (beside `args`) to go "
                f"down dark anyway.")
    return None


def drop_guard(drops: list[dict[str, Any]], entries: list[dict[str, Any]],
               pos: dict | None, *, in_danger: bool = False) -> str | None:
    """The fifth rule as a pure function: ore broken and not picked up, and a plan
    with no collecting entry in it, is refused (override `why`). Not while the last
    episode took damage (`in_danger`): the attacker comes first."""
    if not drops or not entries or in_danger:
        return None
    if any(e.get("why") for e in entries):
        return None
    for e in entries:
        k = entry_kind(e)
        act = set(e.get("action") or {}) if "action" in e else set()
        if k in _COLLECTORS or (_MOVE_KEYS & act) or ("attack" in act):
            return None
    d = max(drops, key=lambda x: x["broke"] - x["picked"])
    row = d["row"]
    from mfm.memory.retrieve import _where
    where = _where(row, pos) or ""
    first = entry_kind(entries[0])
    return (f"refused `{first}`: {d['broke']} {d['item']} broke at step {row.get('first_step')} "
            f"({row['id']}){where} and only {d['picked']} were picked up since -- the drop lies "
            f"in the mined cell (it despawns ~6000 ticks after it fell). Walk into that cell and "
            f"`collect_drops` there BEFORE mining on; nothing in this plan goes there. Or put "
            f"`\"why\": \"<one sentence>\"` on an entry to run it anyway.")


def sword_guard(pos: dict | None, inventory: dict[str, int],
                entries: list[dict[str, Any]]) -> str | None:
    """The fourth rule as a pure function: a descent that ends (or starts) below
    LIGHT_BELOW_Y with no sword carried is refused, unless the entry says `unarmed`.
    lad5 (x2), lad7a and lad7b (2026-09-05/06) all died to a melee mob in their own
    shaft; the chassis's fightback reflex arms only with a sword in the hotbar, and
    none of them had crafted the 2-cobblestone one."""
    if not pos or pos.get("y") is None:
        return None
    inv = {k: int(v or 0) for k, v in (inventory or {}).items()}
    if any(k.endswith("_sword") and n > 0 for k, n in inv.items()):
        return None
    y = float(pos["y"])
    for e in entries:
        k = entry_kind(e)
        if k not in _DESCENTS or e.get("unarmed"):
            continue
        target = (e.get("args") or {}).get("until_y")
        try:
            low = min(y, float(target)) if target is not None else y
        except (TypeError, ValueError):
            low = y
        if low >= LIGHT_BELOW_Y:
            continue
        have = ", ".join(f"{n} x{inv[n]}" for n in ("cobblestone", "stick", "spruce_planks",
                                                     "oak_planks", "birch_planks", "iron_ingot")
                         if inv.get(n))
        return (f"refused `{k}`: it would take you to y {low:.0f} and you carry no sword. "
                f"A melee mob at arm's length in a 1-wide tunnel is what killed the last four "
                f"runs that died; with a sword in your HOTBAR the runner fights it for you, "
                f"without one it can only sprint, and a shaft has nowhere to sprint. "
                f"stone_sword = 2 cobblestone + 1 stick at the table's 3x3 screen; you carry "
                f"{have or 'no cobblestone or sticks yet'}. Craft it and keep it in the "
                f"hotbar, or put `\"unarmed\": true` on the entry (beside `args`) to go "
                f"down without one.")
    return None


def _num(v: Any) -> float | None:
    try:
        return float(v.item() if hasattr(v, "item") else v)
    except (TypeError, ValueError, AttributeError):
        return None


def _xz(pos: dict | None) -> tuple[float, float] | None:
    if not pos or pos.get("x") is None or pos.get("z") is None:
        return None
    return float(pos["x"]), float(pos["z"])


def _hotbar(info: dict) -> list[dict[str, Any]]:
    inv = info.get("inventory") or {}
    out = []
    for slot in range(9):
        it = inv.get(slot) if slot in inv else inv.get(str(slot))
        if not isinstance(it, dict):
            continue
        name = str(it.get("type") or "air")
        qty = _num(it.get("quantity")) or 0
        if name != "air" and qty > 0:
            out.append({"slot": slot, "item": name, "n": int(qty)})
    return out


class EpisodeBridge:
    """The chassis-side owner of the store (see the module docstring)."""

    #: Never auto-close on a tick count: the chassis says when an entry finished.
    _OPEN_ENDED = 10 ** 9

    def __init__(self, memory, codex, ledger, *, retrieval: bool = False,
                 refusal: bool = False) -> None:
        self.memory = memory
        self.codex = codex                      # the store reads `agent.codex.calls`
        self.ledger = ledger
        self.store = EpisodeStore(memory.root)
        self.mfm_memory_note = MFM_MEMORY_NOTE
        # The retrieval flag: the turn prompt carries `recall()` when it is non-empty.
        # Off, the arm is exactly the lad1/lad2 mfm arm.
        self.retrieval = bool(retrieval)
        self.recalls = 0
        # The refusal flag: `refuse()` vetoes a plan from the record (see
        # MFM_REFUSAL_NOTE). Independent of `retrieval`; both off = the lad2 arm.
        self.refusal = bool(refusal)
        self.refusal_by_rule: Counter[str] = Counter()
        self.overrides = 0
        self._refused: Counter[tuple] = Counter()
        # Earlier lives' records under previous/ (previous.py); None until
        # `seed_previous` is given seed dirs.
        self.previous: PreviousLives | None = None
        self._obs: Observation | None = None
        self._tick_prev_pos: dict | None = None
        self._scratch = memory.attach_dir / "episode_frame.png"
        self.frames_written = 0

    # -- what the chassis calls --------------------------------------------------

    def _observation(self, info: dict, step: int, png: bytes | None) -> Observation:
        attachment = None
        if png:
            # A fresh file per open: the store hard-links the attachment into the
            # episode, and the attach frame is rewritten in place every turn, so
            # linking THAT would make every episode's image the latest view.
            self._scratch.parent.mkdir(parents=True, exist_ok=True)
            self._scratch.unlink(missing_ok=True)
            self._scratch.write_bytes(png)
            attachment = str(self._scratch)
            self.frames_written += 1
        return Observation(step=step, attachment=attachment,
                           state={"pos": location(info)}, raw={"info": info})

    def initial(self, info: dict, step: int, png: bytes | None) -> None:
        self._obs = self._observation(info, step, png)
        self.store.initial(self, self._obs)
        self._scratch.unlink(missing_ok=True)

    def observe(self, info: dict, step: int) -> None:
        self._obs = Observation(step=step, attachment=None,
                                state={"pos": location(info)}, raw={"info": info})
        self.store.observe(self, self._obs)

    def plan(self, turn: int, briefing: str | None, plan_text: str | None) -> None:
        self.store.plan(self, SimpleNamespace(briefing=briefing or "", think=plan_text or ""))

    def open(self, entry: dict[str, Any], index: int, total: int, info: dict,
             step: int, png: bytes | None) -> None:
        if any(entry.get(k) for k in ("why", "leave_table", "unlit", "unarmed")):
            self.overrides += 1
        self._obs = self._observation(info, step, png)
        item = {"tick": 1, "ticks": self._OPEN_ENDED, "entry": entry,
                "entry_index": index + 1, "entries_total": total}
        self.store.act(self, item)
        self._scratch.unlink(missing_ok=True)

    def note(self, text: str) -> None:
        self.store.note(self, text)

    def close_entry(self, *, events: list[str], notes: list[str]) -> None:
        for n in notes:
            self.store.note(self, n)
        tags = ("broke",) if any(e.split(" ", 1)[0] in _BROKE_EVENTS for e in events) else ()
        self.store.close(self, tags=tags, events=list(events))

    def flush(self, step: int) -> None:
        if self.store._open is not None:
            obs = self._obs if self._obs is not None and self._obs.step == step else \
                Observation(step=step, attachment=None, state={"pos": None}, raw={"info": {}})
            self.store.refill(self, obs)

    def finish(self) -> None:
        self.store.close(self)

    def refuse(self, entries: list[dict[str, Any]], pos: dict | None,
               inventory: dict[str, int],
               placed_cells: dict[str, tuple] | None = None) -> str | None:
        """The refusal text for this plan, or None to let it run (see MFM_REFUSAL_NOTE).

        Whole-plan, like the governor's veto: dropping one entry out of a composite
        corrupts the plan instead of saving its steps. Each streak and each placement
        is refused at most REFUSE_CAP times, so a model that will not say `why` is
        slowed, not stopped."""
        if not self.refusal or not entries:
            return None
        rows = self.store.closed
        root = self.memory.root
        placements = left_behind(rows, root)
        unopened = False
        if placements:
            since = placements[-1]["step"] or 0
            unopened = any("no screen opened" in n
                           for r in rows if (r.get("first_step") or 0) > since
                           and r.get("action_kind") == "use_until_gui"
                           for n in notes_of(root, r))
        note = descent_guard(placements, pos, inventory, entries, placed_cells, unopened)
        if note:
            key = ("descent", note.split("(")[1].split(")")[0])     # the placement id
            if self._refused[key] < REFUSE_CAP:
                self._refused[key] += 1
                self.refusal_by_rule["left_behind"] += 1
                return "harness: " + note
        note = light_guard(pos, inventory, entries)
        if note:
            if self._refused[("light",)] < REFUSE_CAP:
                self._refused[("light",)] += 1
                self.refusal_by_rule["unlit"] += 1
                return "harness: " + note
        elif int((inventory or {}).get("torch", 0) or 0) > 0:
            self._refused.pop(("light",), None)                     # torches: the rule re-arms
        hurt = bool(rows) and "damage" in (rows[-1].get("tags") or [])
        note = drop_guard(uncollected(rows, root, _ORE_DROPS), entries, pos, in_danger=hurt)
        if note:
            key = ("drop", note.split("(")[1].split(")")[0])          # the breaking episode
            if self._refused[key] < REFUSE_CAP:
                self._refused[key] += 1
                self.refusal_by_rule["uncollected"] += 1
                return "harness: " + note
        note = sword_guard(pos, inventory, entries)
        if note:
            if self._refused[("sword",)] < REFUSE_CAP:
                self._refused[("sword",)] += 1
                self.refusal_by_rule["unarmed"] += 1
                return "harness: " + note
        elif any(k.endswith("_sword") for k, v in (inventory or {}).items() if v):
            self._refused.pop(("sword",), None)
        current = {s["kind"]: s for s in
                   streaks(rows, min_len=REFUSE_AT, ignore=RECALL_IGNORE_KINDS,
                           movers=_MOVERS, openers=_OPENERS)}
        for key in [k for k in self._refused if k[0] == "streak"
                    and (k[1] not in current or current[k[1]]["since_step"] != k[2])]:
            del self._refused[key]                       # that streak broke or moved on
        for e in entries:
            kind = entry_kind(e)
            s = current.get(kind)
            if s is None:
                continue
            if e.get("why"):
                # A `why` that already ran and changed nothing is spent: the next one on
                # the same streak is refused (twice), with the spent claim quoted, so a
                # false claim costs a tick and a new sentence instead of buying the loop.
                burned = burned_override(root, s["rows"])
                if burned is None:
                    continue
                b, said = burned
                key = ("streak", kind, s["since_step"], "burned", b["id"])
                if self._refused[key] >= REFUSE_CAP:
                    continue
                self._refused[key] += 1
                self.refusal_by_rule["burned_why"] += 1
                ticks = (b.get("last_step") or 0) - (b.get("first_step") or 0)
                return (f"harness: refused `{kind}` again -- at step {b.get('first_step')} "
                        f"({b['id']}) you ran it past the refusal with \"{said}\"; it ran "
                        f"{ticks} ticks and changed nothing, and it has changed nothing since "
                        f"({s['n']} calls, since step {s['since_step']}"
                        f"{_where_ok(s, pos)}).{hint_for(kind, _last_note(root, s))} Say "
                        f"what is different NOW -- something you can see -- or propose "
                        f"something else.")
            key = ("streak", kind, s["since_step"])
            if self._refused[key] >= REFUSE_CAP:
                continue
            self._refused[key] += 1
            self.refusal_by_rule["streak"] += 1
            return (f"harness: refused `{kind}` -- {streak_line(s, root, pos)}"
                    f"{hint_for(kind, _last_note(root, s))} Propose something else, or "
                    f"give the entry `\"why\": \"<what is different this time>\"` to run "
                    f"it anyway.")
        return None

    def seed_previous(self, seeds: list) -> None:
        """Carry the earlier lives' records in (the MFM carry)."""
        self.previous = PreviousLives(self.memory.root)
        self.previous.seed([Path(s) for s in seeds])

    def recall(self, info: dict) -> str:
        """The retrieval block for the turn about to run, from the rows the store
        already holds; "" when there is nothing to recall or the flag is off."""
        if not self.retrieval:
            return ""
        pos = _xz(location(info))
        block = recall_block(self.store.closed, self.memory.root, pos=pos,
                             ignore_kinds=RECALL_IGNORE_KINDS, movers=_MOVERS,
                             openers=_OPENERS)
        if block:
            self.recalls += 1
        return block

    def audit(self) -> dict[str, Any]:
        out = self.store.audit(self)
        # The chassis backend counts the tool in its rollout scan (`vision_audit`,
        # which `report` calls first); the store's own getattr finds nothing there.
        counts = getattr(self.codex, "_tool_error_counts", None) or {}
        out["episodes_tool_calls"] = counts.get("episodes_tool_calls")
        out["frames_written"] = self.frames_written
        out["retrieval"] = self.retrieval
        out["recalls"] = self.recalls
        out["refusal"] = self.refusal
        out["refusals"] = dict(self.refusal_by_rule)
        out["overrides"] = self.overrides
        if self.previous is not None:
            out["previous"] = self.previous.audit()
        return out

    # -- the store's hooks (what is Minecraft about an episode) ---------------------

    def episode_state(self, obs: Observation) -> dict[str, Any]:
        info = obs.raw["info"] or {}
        pos = obs.state["pos"]
        here, before = _xz(pos), _xz(self._tick_prev_pos)
        moved = math.dist(here, before) if here and before else 0.0
        self._tick_prev_pos = pos
        stats = info.get("location_stats") or {}
        vitals: dict[str, Any] = {}
        for label, key, src in (("health", "health", info), ("food", "food_level", info),
                                ("light", "light_level", stats)):
            v = _num(src.get(key))
            if v is not None:
                vitals[label] = v
        if stats.get("can_see_sky") is not None:
            vitals["sky"] = str(stats["can_see_sky"]).lower() == "true"
        mobs = info.get("mobs")
        mob_counts = None
        if isinstance(mobs, list):
            mob_counts = dict(Counter(
                str((m.get("name") or m.get("type") or "?") if isinstance(m, dict) else m)
                for m in mobs))
        done = [r["identity"] for r in self.ledger.cfg if r["identity"] in self.ledger.achieved]
        todo = [r["identity"] for r in self.ledger.cfg if r["identity"] not in self.ledger.achieved]
        gui = info.get("isGuiOpen")
        return {
            "step": obs.step, "pos": pos, "moved": round(moved, 3),
            "inventory": inventory_counts(info), "hotbar": _hotbar(info),
            "gui_open": bool(gui) if gui is not None else None,
            "mainhand": ((info.get("equipped_items") or {}).get("mainhand") or {}).get("type"),
            "vitals": vitals, "mobs": mob_counts,
            "goals": {"done": done, "next": todo[0] if todo else None},
            "verified": f"{len(done)}/{len(self.ledger.cfg)}",
        }

    def episode_action(self, item: dict[str, Any]) -> Any:
        return item["entry"]

    def episode_action_kind(self, item: dict[str, Any]) -> str | None:
        entry = item["entry"]
        if "procedure" in entry:
            return str(entry["procedure"])
        act = entry.get("action") or {}
        keys = [k for k, v in act.items() if v not in (0, [0, 0], [0.0, 0.0])]
        return "+".join(keys) or "noop"

    def episode_outcome(self, entry: Any, first: dict[str, Any], last: dict[str, Any],
                        notes: list[str], flushed: bool) -> tuple[dict[str, Any], list[str], str]:
        here, before = _xz(last.get("pos")), _xz(first.get("pos"))
        moved = math.dist(here, before) if here and before else 0.0
        y0 = _num((first.get("pos") or {}).get("y"))
        y1 = _num((last.get("pos") or {}).get("y"))
        descended = (y0 - y1) if y0 is not None and y1 is not None else 0.0
        inv0, inv1 = first.get("inventory") or {}, last.get("inventory") or {}
        delta = {k: inv1.get(k, 0) - inv0.get(k, 0) for k in sorted(set(inv0) | set(inv1))
                 if inv1.get(k, 0) != inv0.get(k, 0)}
        done0 = set((first.get("goals") or {}).get("done") or [])
        done1 = set((last.get("goals") or {}).get("done") or [])
        transition = sorted(done1 - done0) or None
        entry = entry or {}
        if "procedure" in entry:
            movement = str(entry["procedure"]) in _MOVERS
        else:
            movement = bool(_MOVE_KEYS & set(entry.get("action") or {}))
        tags = []
        if transition:
            tags.append("milestone")
        if delta:
            tags.append("inventory_changed")
        if movement and moved < 0.5 and abs(descended) < 0.5:
            tags.append("stuck")
        if last.get("gui_open"):
            tags.append("gui")
        h0 = (first.get("vitals") or {}).get("health")
        h1 = (last.get("vitals") or {}).get("health")
        if h0 is not None and h1 is not None and h1 < h0:
            tags.append("damage")
        summary = (f"{describe_entry(entry)}: moved {moved:.1f}" if entry else "no entry")
        if abs(descended) >= 0.5:
            summary += f", descended {descended:.1f}"
        if delta:
            summary += f", inv {delta}"
        if transition:
            summary += f", milestone {transition}"
        return ({"moved": round(moved, 2), "descended": round(descended, 2),
                 "inventory_delta": delta, "milestone_transition": transition,
                 "verified_after": last.get("verified")}, tags, summary)

    def episode_index_fields(self, first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
        pos = first.get("pos") or {}
        return {"x": pos.get("x"), "y": pos.get("y"), "z": pos.get("z"),
                "gui_open": first.get("gui_open")}
