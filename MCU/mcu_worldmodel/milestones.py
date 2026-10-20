"""Ground truth: what the environment says has actually happened.

The two long-horizon tasks are scored by milestone depth, not pass/fail -- each config
in `MCU_benchmark/task_configs/tasks/` lists an ordered progression (24 for the
dragon, 10 for the diamond) and the run's score is how far down it got. The rules are
deltas on MineRL's own statistics (`mine_block`, `craft_item`, `pickup`, `kill_entity`),
which is the same source `RewardsCallback` uses, so this ledger and the official
`MilestoneTrackerCallback` cannot disagree about what happened.

This module exists because the agent needs that signal *during* the episode, not only in
the JSON written at the end. Two consumers:

    the prompt        "9/10 verified; next target: diamond" -- so the model plans against
                      real progress rather than its own narrative of it
    the log           a `[EVENT] MILESTONE <name> verified` line in logs.txt when one lands

Nothing here ever reads a model output. That is the whole point: a claim and its check
must not share a source.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml
from loguru import logger


def _stat(info: dict, event: str, obj: str) -> float:
    """One statistic, defaulting to 0. Mirrors RewardsCallback._get_obj_num exactly --
    including the np.ndarray unwrap, since ObserveFromFullStats returns 0-d arrays."""
    if event not in info:
        return 0.0
    bucket = info[event]
    if obj not in bucket:
        return 0.0
    res = bucket[obj]
    return float(res.item()) if isinstance(res, np.ndarray) else float(res)


class MilestoneLedger:
    """Tracks the ordered progression and reports it as ground truth."""

    def __init__(self, reward_cfg: list[dict[str, Any]], task_name: str = "") -> None:
        self.cfg = list(reward_cfg or [])
        self.task_name = task_name
        self.order = [c["identity"] for c in self.cfg]
        self.achieved: dict[str, int] = {}       # identity -> step first achieved
        self._prev: dict[str, Any] = {}
        self._prev_stats: dict[tuple[str, str], float] = {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MilestoneLedger":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(data.get("milestone_reward_cfg") or [],
                   task_name=Path(path).stem)

    def reset(self, info: dict) -> None:
        self._prev = dict(info)
        self.achieved = {}

    def update(self, info: dict, step: int) -> list[dict[str, Any]]:
        """Advance the ledger one env step. Returns the milestones newly achieved.

        Two sources, in priority order:

        1. `info['milestones']` when the host publishes it. Those bits come from the
           callback that *scores* the run, so agreeing with them is agreeing with the
           result. It also repairs a real divergence: the green agent truncates each
           rule's `objects` list to four when it builds `milestone_spec`, and
           `kill_ender_dragon`'s `mine_log` names seven log types -- so a ledger recomputed
           from the spec would score a jungle_log as nothing while the environment banked
           it, and the agent would keep chopping a milestone it had already passed.
        2. Deltas on the raw statistics otherwise, which is what a run without the
           extended observation has. Deltas rather than absolute values because
           `max_reward_times` is 1 everywhere: a milestone fires the first time its
           statistic moves, and an absolute test would re-fire on every later log.
        """
        published = info.get("milestones")
        published = published if isinstance(published, dict) else None
        fired = []
        for rule in self.cfg:
            ident = rule["identity"]
            if ident in self.achieved:
                continue
            if published is not None:
                if ident not in published:
                    continue
                try:
                    hit = int(published[ident]) == 1
                except (TypeError, ValueError):
                    hit = False
                if hit:
                    self.achieved[ident] = step
                    fired.append({"kind": "milestone", "identity": ident,
                                  "event": rule["event"], "objects": rule["objects"]})
                    logger.success(f"[milestone] {ident} at step {step} "
                                   f"({len(self.achieved)}/{len(self.cfg)}) [host-verified]")
                continue
            event = rule["event"]
            delta = 0.0
            for obj in rule["objects"]:
                delta += _stat(info, event, obj) - _stat(self._prev, event, obj)
            if delta > 0:
                self.achieved[ident] = step
                fired.append({"kind": "milestone", "identity": ident,
                              "event": event, "objects": rule["objects"]})
                logger.success(f"[milestone] {ident} at step {step} "
                               f"({len(self.achieved)}/{len(self.cfg)})")
        self._prev = dict(info)
        return fired

    #: Statistic buckets worth a ground-truth line each time they move. `use_item` is in:
    #: placing a block is a `use_item` on it, which is how the agent learns its crafting
    #: table actually went down.
    STAT_EVENTS = ("mine_block", "craft_item", "pickup", "break_item", "use_item",
                   "kill_entity")

    def stat_events(self, info: dict) -> list[dict[str, Any]]:
        """Every statistic that moved this step, not only the milestone-matching ones.

        `events.jsonl` was documented to the agent as "one line per discrete world event"
        and actually carried only milestones -- one line in 1,900 steps of one run. The
        gap bit twice: crafting planks (not a milestone) would leave the agent's declared
        authoritative channel silent, reading as a failed craft; and a chop that landed
        produced nothing greppable until the [INV] line at entry end. This closes the gap
        with deltas on the same raw statistics the milestones use.
        """
        fired: list[dict[str, Any]] = []
        for event in self.STAT_EVENTS:
            bucket = info.get(event)
            if not isinstance(bucket, dict):
                continue
            for item, val in bucket.items():
                cur = float(val.item()) if isinstance(val, np.ndarray) else float(val)
                if cur <= 0:
                    continue
                prev = self._prev_stats.get((event, item), 0.0)
                if cur > prev:
                    fired.append({"kind": "stat", "event": event, "item": item,
                                  "delta": round(cur - prev, 2)})
                self._prev_stats[(event, item)] = cur
        return fired

    # -- views ------------------------------------------------------------

    def is_verified(self, identity: str) -> bool:
        return identity in self.achieved

    def all_done(self) -> bool:
        return len(self.achieved) == len(self.cfg) and bool(self.cfg)

    def next_target(self) -> dict[str, Any] | None:
        """The first unachieved rule in config order.

        Config order, deliberately, not "any unachieved rule". Both progressions are
        genuine dependency chains -- you cannot craft a stone pickaxe before mining
        cobblestone -- so the first gap is the one thing worth working on, and naming it
        is what keeps a 12,000-step episode from wandering.
        """
        for rule in self.cfg:
            if rule["identity"] in self.achieved:
                continue
            return rule
        return None

    def progress_line(self) -> str:
        """One line of scored truth -- including that the ORDER is presentation only.

        The score is the COUNT of achieved milestones; nothing requires taking them in
        list order. Four straight runs finished 5/10 with 8+ cobblestone in hand and no
        furnace, because "Next unmet: mine_iron_ore" (the first gap in list order) sent
        every endgame chasing iron while a +1 sat one craft away. The two 6/10 runs are
        exactly the ones that banked the furnace "out of order".
        """
        if not self.cfg:
            return ("No milestone list is configured for this task: progress is what you "
                    "actually accomplish, verified on the game's statistics.")
        nxt = self.next_target()
        advice = (" -- bank whichever are already within reach (a furnace needs only "
                  "8 cobblestone) before chasing the next in list order.")
        head = (f"Environment-verified progress: {len(self.achieved)}/{len(self.cfg)} "
                f"milestones. Score = COUNT achieved, in ANY order{advice}")
        if nxt is None:
            return head + " ALL MILESTONES VERIFIED."
        return (head + f" First unmet in list order: `{nxt['identity']}` "
                f"({nxt['event']} of {'/'.join(nxt['objects'][:4])}).")

    def progress_block(self) -> str:
        """The full ordered checklist for the prompt. Both lists are short enough to show
        whole (10 and 24), and showing the *unmet* ones is what stops the agent
        re-deriving the tech tree from scratch every turn."""
        lines = []
        for rule in self.cfg:
            ident = rule["identity"]
            if ident in self.achieved:
                lines.append(f"  [x] {ident} (step {self.achieved[ident]})")
            else:
                lines.append(f"  [ ] {ident} <- {rule['event']}: "
                             f"{', '.join(rule['objects'][:4])}")
        return "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        return {
            "task": self.task_name,
            "milestones_achieved": len(self.achieved),
            "total_milestones": len(self.cfg),
            "completion_rate": (len(self.achieved) / len(self.cfg)) if self.cfg else 0.0,
            "achieved": dict(self.achieved),
            "order": self.order,
        }


def slot_is_empty(entry) -> bool:
    """True when a player-inventory slot entry holds nothing.

    The ONE predicate every reader of `info['inventory']` must share. Empty slots come
    over the wire as `{"type": "none", "quantity": 0}` in this engine (gui.find_slots
    learned that first); `sim.reset()` on a compute node reports them as "air". Three
    readers (the prompt's free-slot count, the
    close-refusal slot hint, stow_items' target list) accepted only "air" -- so from the
    first turn of every live arm the Inventory line read "0 slots free" with nothing
    carried, and stow_items refused every call with "every inventory slot is full".
    One run spent its last 7,000 steps freeing slots that were never taken. A zero quantity
    is empty whatever the type string says.
    """
    if not isinstance(entry, dict):
        return False
    name = entry.get("type")
    if (not name) or str(name) in ("none", "air"):
        return True
    qty = entry.get("quantity", 0)
    try:
        qty = int(qty.item()) if isinstance(qty, np.ndarray) else int(qty)
    except (TypeError, ValueError):
        return False
    return qty <= 0


def inventory_counts(info: dict) -> dict[str, int]:
    """`info['inventory']` aggregated to {item: total count}.

    The wire shape is **slot-keyed**, not item-keyed: `PlainInventoryObservation` returns
    `{slot_id: {"type": name, "quantity": n}}` across 36 slots. Aggregating is therefore
    required, not cosmetic -- reading it as {item: count} yields slot indices as item names
    and a total of zero for everything.

    Empty slots are dropped (see `slot_is_empty`), so a model shown the raw dict never
    concludes it is carrying thirty air.
    """
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return {}
    out: dict[str, int] = {}
    for slot in inv.values():
        if not isinstance(slot, dict) or slot_is_empty(slot):
            continue
        name = slot.get("type")
        qty = slot.get("quantity", 0)
        qty = int(qty.item()) if isinstance(qty, np.ndarray) else int(qty)
        if qty > 0:
            out[str(name)] = out.get(str(name), 0) + qty
    return out


def hotbar_line(info: dict) -> str:
    """What is in each hotbar slot, as the prompt shows it.

    Slots 0-8 are the hotbar, and `hotbar.1`..`hotbar.9` select them. The agent cannot mine
    stone with a pickaxe it has not selected, and it has no other way to learn which number
    to press -- the 640x360 frame shows the hotbar, but reading item icons off it reliably
    is exactly the kind of visual inference the [STATE] channel exists to replace.
    """
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return "unknown"
    parts = []
    for slot in range(9):
        entry = inv.get(slot) or inv.get(str(slot))
        if not isinstance(entry, dict) or slot_is_empty(entry):
            continue
        name = entry.get("type")
        qty = entry.get("quantity", 0)
        qty = int(qty.item()) if isinstance(qty, np.ndarray) else int(qty)
        if qty > 0:
            parts.append(f"hotbar.{slot + 1}={name}x{qty}")
    return ", ".join(parts) or "empty"


def slot_map(info: dict) -> dict[int, tuple[str, int]]:
    """Every occupied player slot (0-35, the [INV] ids): slot -> (item, count)."""
    inv = info.get("inventory")
    out: dict[int, tuple[str, int]] = {}
    if not isinstance(inv, dict):
        return out
    for slot in range(36):
        entry = inv.get(slot) or inv.get(str(slot))
        if not isinstance(entry, dict) or slot_is_empty(entry):
            continue
        qty = entry.get("quantity", 0)
        qty = int(qty.item()) if isinstance(qty, np.ndarray) else int(qty)
        if qty > 0:
            out[slot] = (str(entry.get("type")), qty)
    return out


def main_rows_line(info: dict) -> str:
    """What is in each main-row slot (9-35), as the mfm arm shows it beside the
    hotbar: with no `craft` to find the ingredients, a click needs the slot NUMBER."""
    parts = [f"{slot}={name}x{n}" for slot, (name, n) in slot_map(info).items() if slot >= 9]
    return ", ".join(parts) or "empty"


def held_line(info: dict) -> str:
    """The mainhand item with its remaining durability, from `equipped_items`.

    One run's wooden pickaxe broke at step 5081 mid iron-hunt with no plank reserve;
    the run ended 4/10 holding 22 cobblestone it could no longer craft into anything.
    `damage`/`maxDamage` were on the wire the whole time -- "N uses left" turns a tool
    break from a post-mortem into a deadline a replacement can be planned against.
    """
    eq = info.get("equipped_items")
    hand = eq.get("mainhand") if isinstance(eq, dict) else None
    if not isinstance(hand, dict):
        return "unknown"
    name = str(hand.get("type") or "none")
    if name in ("none", "air"):
        return "empty hand"

    def _num(v):
        try:
            return int(v.item()) if isinstance(v, np.ndarray) else int(v)
        except (TypeError, ValueError):
            return None

    dmg, mx = _num(hand.get("damage")), _num(hand.get("maxDamage"))
    if dmg is None or mx is None or mx <= 0:
        return name
    left = mx - dmg
    warn = " -- NEARLY BROKEN: craft the replacement NOW" if left <= 12 else ""
    return f"{name} ({left}/{mx} uses left{warn})"


def vitals(info: dict) -> str:
    """Health and food. Both tasks are long enough to starve or be killed in, and a run
    that dies at step 3,000 with nine milestones is scored on the nine -- so these belong
    in front of the agent rather than only in the frame."""
    def g(key):
        v = info.get(key)
        if v is None:
            return None
        return float(v.item()) if isinstance(v, np.ndarray) else float(v)
    hp, food = g("health"), g("food_level")
    bits = []
    if hp is not None:
        bits.append(f"health={hp:.0f}/20")
    if food is not None:
        bits.append(f"food={food:.0f}/20")
    return " ".join(bits) or "unknown"


def nearby_mobs(info: dict, limit: int = 8) -> str:
    """Entities the server reports near the player.

    Defensively shaped: `info['mobs']` is a list of dicts in the builds seen here, but the
    exact field names vary, so anything unrecognised degrades to a count rather than
    raising. Worth surfacing because the dragon task is scored partly on kills, and because
    "there is a creeper behind you" is not reliably visible in the frame.
    """
    mobs = info.get("mobs")
    if mobs is None:
        # The channel itself is absent (human-parity info does not carry an off-screen
        # radar). Distinct from an empty list on purpose: "none reported" would read as
        # ground truth that nothing is nearby, which the agent has no basis for.
        return "not reported -- read the frame"
    if not mobs:
        return "none reported"
    try:
        names: dict[str, int] = {}
        for m in mobs:
            if isinstance(m, dict):
                n = m.get("name") or m.get("type") or m.get("mob_type") or "?"
            else:
                n = str(m)
            names[str(n)] = names.get(str(n), 0) + 1
        top = sorted(names.items(), key=lambda kv: -kv[1])[:limit]
        return ", ".join(f"{n}x{c}" for n, c in top)
    except Exception:
        return f"{len(mobs)} reported"


def location(info: dict) -> dict[str, float] | None:
    """`info['location_stats']` as the {x,y,z,pitch,yaw} shape memory.state_line wants."""
    loc = info.get("location_stats")
    if not isinstance(loc, dict):
        return None

    def g(*names):
        for n in names:
            if n in loc:
                v = loc[n]
                return float(v.item()) if isinstance(v, np.ndarray) else float(v)
        return 0.0

    if not any(n in loc for n in ("xpos", "x")):
        return None
    return {"x": g("xpos", "x"), "y": g("ypos", "y"), "z": g("zpos", "z"),
            "pitch": g("pitch"), "yaw": g("yaw")}
