"""The MFM arm's adapter: mfm's episode store, driven from the chassis's own hook points.

`--memory mfm` is one append-only `logs.txt` on the chassis plus the
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


from mfm.agent.base import Observation
from mfm.memory.retrieve import recall_block
from mfm.memory.store import EpisodeStore

from mcu_worldmodel.actions import describe_entry
from mcu_worldmodel.milestones import inventory_counts, location
from mcu_worldmodel.previous import PreviousLives

#: Counted in the rollouts: how often the model ran the query tool.
ROLLOUT_EPISODES_TOOL = re.compile(r"tools/episodes\.py")

#: Procedures whose point is to move; an entry of one that moved under half a block
#: gets the `stuck` tag, the same rule the raw movement keys get. The registered
#: names (procedures.py) -- the first list had "goto" for `go_to`, so no go_to entry
#: was ever tagged stuck.
_MOVERS = frozenset({
    "go_to", "travel", "mine_forward", "strip_mine", "stair_down", "dig_down",
    "dig_up", "pillar_up", "walk", "explore", "swim_up", "climb", "descend", "tunnel",
    "run",
})
_MOVE_KEYS = frozenset({"forward", "back", "left", "right", "jump", "sprint"})

#: The paragraph the MFM arm adds to the log protocol text (`prompts._LOG_CONTRACT`).
#: Kept here beside the store it describes; `prompts._mfm_contract` splices it in.
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

#: `frames`: the arm can read frames at pixel level.
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
[--radius R] | --tag stuck | --action go_to | --grep text` lists matching episodes
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

#: Entry kinds whose normal outcome is "nothing changed": a streak of them is not a
#: loop. Everything else (harvest_tree, dig_down, craft, collect_drops, a held raw
#: key...) is meant to change the world or the inventory when it works.
RECALL_IGNORE_KINDS = frozenset({
    "look", "look_abs", "look_at", "equip_hotbar", "close_inventory",
    "inventory", "noop", "scan_around", "aim_at_ore", "aim_at_tree",
    "wait", "cursor_to", "cursor_to_cell", "cursor_to_slot",
})
#: Entries whose job is to open a screen: they changed something iff a screen is
#: open at their end (the `gui` tag). Not bookkeeping: five `use_until_gui` that
#: opened nothing is the loop one run sat in.
_OPENERS = frozenset({"use_until_gui", "open_inventory", "place_and_open"})


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

    def __init__(self, memory, codex, ledger, *, retrieval: bool = False) -> None:
        self.memory = memory
        self.codex = codex                      # the store reads `agent.codex.calls`
        self.ledger = ledger
        self.store = EpisodeStore(memory.root)
        self.mfm_memory_note = MFM_MEMORY_NOTE
        # `retrieval`: the turn prompt carries `recall()` when it is non-empty.
        self.retrieval = bool(retrieval)
        self.recalls = 0
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
        self.store.close(self, events=list(events))

    def flush(self, step: int) -> None:
        if self.store._open is not None:
            obs = self._obs if self._obs is not None and self._obs.step == step else \
                Observation(step=step, attachment=None, state={"pos": None}, raw={"info": {}})
            self.store.refill(self, obs)

    def finish(self) -> None:
        self.store.close(self)

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
        summary = f"{describe_entry(entry)}: moved {moved:.1f}" if entry else "no entry"
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
