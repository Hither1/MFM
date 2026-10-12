"""Parse and validate the `actions.json` one turn produces.

Two entry shapes, because the agent works at two levels:

    {"action": {"forward": 1}, "repeat": 20}          a raw action, held N ticks
    {"procedure": "dig_down", "args": {"n": 40}}      a named macro from procedures.py

The raw form is a MineRL action dict held for `repeat` ticks. The procedure
form is what makes crafting expressible at all (see procedures.py) and what lets one turn
cover a few hundred ticks instead of forty -- which is the difference between 12,000 steps
costing 300 model turns and costing 3,000.

Validation is deliberately lenient about *entries* and strict about *keys*: an
unrecognised key is dropped with a warning and the rest of the entry still runs, because
a whole plan discarded over one typo costs the episode a turn and teaches the model
nothing about which key was wrong. What is never lenient is the step cap -- a turn cannot
run more environment steps than it was budgeted, or the plan queue stops being a bound on
how long the agent goes without looking.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Collection

from loguru import logger

from mcu_worldmodel import procedures as P

# The keys the *real* env action space accepts, which is not the list `entry.py` advertises
# for `action_type="env"` -- that hardcoded dict omits `pickItem`, `chat`, `mobs` and
# `voxels`, all of which the installed handlers do provide. The authority is
# `spec.actionables`, not entry.py.
#
# Missing keys are harmless: `_multiagent._process_action` skips any handler whose name is
# absent from the dict, so a partial action is valid and there is no need to send a fully
# populated no-op.
VALID_KEYS = {
    "attack", "back", "forward", "jump", "left", "right", "sneak", "sprint", "use",
    "inventory", "pickItem", *(f"hotbar.{i}" for i in range(1, 10)),
}

# Added by mcu_worldmodel.craft_env when it patches the spec. Gated on that patch being
# applied, because sending `equip` to an unpatched env silently does nothing (the handler
# is absent, so `_process_action` skips the key) -- which would look like the engine
# ignoring a valid command.
OPTIONAL_KEYS = {"drop"}

# Present in the action space, never offered to the agent. `chat` is a command channel:
# a from-scratch run that can send `/give` can hand itself the entire tech tree, and the
# two from-scratch task configs (diamond, dragon) are `custom_init_commands: []` precisely
# so that nothing does; the portal task's init commands lay its pad and hand out its
# materials. `mobs` and
# `voxels` are observation-region queries rather than actions, and the runner sets them.
FORBIDDEN_KEYS = {"chat", "mobs", "voxels"}

# Not in the action space at all: the engine implements the verbs (`EnvServer` has branches
# for ESC and swapHands) but no INVERSE_KEYMAP entry exists to bind them, so no handler can
# be installed. `craft`/`nearbyCraft`/`nearbySmelt`/`place` are absent from the engine
# entirely -- see craft_env.py.
UNSUPPORTED_KEYS = {"ESC", "swapHands", "swap_hands", "pick_item", "dwheel",
                    "craft", "nearbyCraft", "nearbySmelt", "place",
                    # The engine HAS an `equip` branch, but it parses a number while
                    # MineRL's EquipAction sends an item name, so the handler cannot be
                    # installed (it breaks reset()). Listed here rather than in
                    # OPTIONAL_KEYS because an uninstalled key is silently skipped by
                    # `_process_action` -- the agent would see no error and no effect,
                    # which is worse than a refusal. Wield things with `hotbar.N`.
                    "equip"}


class ActionPlan:
    def __init__(self, entries: list[dict[str, Any]], steps: list[dict[str, Any]],
                 notes: list[str] | None = None) -> None:
        self.entries = entries
        self.steps = steps
        self.notes = notes or []

    def __len__(self) -> int:
        return len(self.steps)

    def __bool__(self) -> bool:
        return bool(self.steps)


def _clean_action(raw: dict[str, Any], notes: list[str],
                  allow_optional: bool = False) -> dict[str, Any] | None:
    a = P.noop()
    for key, value in raw.items():
        if key == "camera":
            try:
                pitch, yaw = float(value[0]), float(value[1])
            except (TypeError, ValueError, IndexError):
                notes.append(f"bad camera value {value!r}, ignored")
                continue
            # Pitch is an absolute clamp in-game; yaw wraps. Normalising here rather than
            # rejecting keeps a 270-degree turn meaning what the model meant by it.
            pitch = max(-90.0, min(90.0, pitch))
            yaw = ((yaw + 180.0) % 360.0) - 180.0
            a["camera"] = [pitch, yaw]
        elif key in VALID_KEYS or (key in OPTIONAL_KEYS and allow_optional):
            try:
                a[key] = 1 if int(value) else 0
            except (TypeError, ValueError):
                notes.append(f"non-numeric value for {key!r}, ignored")
        elif key in FORBIDDEN_KEYS:
            notes.append(f"`{key}` is not available to you; dropped")
        elif key in UNSUPPORTED_KEYS:
            notes.append(f"`{key}` is not implemented by this engine; dropped")
        else:
            notes.append(f"unknown action key {key!r}; dropped")
    # Mutually exclusive pairs, resolved rather than rejected: pressing both is a no-op
    # in-game, so silently keeping them would spend ticks doing nothing.
    for x, y in (("forward", "back"), ("left", "right")):
        if a[x] and a[y]:
            a[x] = a[y] = 0
            notes.append(f"`{x}`+`{y}` cancel out; both cleared")
    hot = [k for k in a if k.startswith("hotbar.") and a[k]]
    if len(hot) > 1:
        for k in hot[1:]:
            a[k] = 0
        notes.append(f"multiple hotbar slots set; kept {hot[0]}")
    return a


#: Optional keys an entry may carry past the parser, unread by the executor: the
#: mfm arm's refusal rules (mcu_worldmodel/episodes.py) let an entry through when it
#: states `why` this time is different, or `leave_table` for a descent without the
#: table. Kept on the entry so the episode's action.json records the model's reason.
OVERRIDE_KEYS = ("why", "leave_table")


def _overrides(entry: dict[str, Any]) -> dict[str, Any]:
    """The override keys, from the entry or from inside its `args` (one run put
    `leave_table` in `args` and the procedure rejected the whole entry as a bad
    argument -- the note said "give the entry", which reads either way)."""
    args = entry.get("args") if isinstance(entry.get("args"), dict) else {}
    out = {k: args.pop(k) for k in OVERRIDE_KEYS if k in args}
    out.update({k: entry[k] for k in OVERRIDE_KEYS if k in entry})
    return out


def parse_actions(raw_text: str, *, entry_cap: int = 40, repeat_cap: int = 200,
                  step_cap: int = 400, allow_optional: bool = False,
                  info: dict[str, Any] | None = None,
                  cursor: Any = None,
                  own_expand: Callable[[str, dict[str, Any]],
                                       tuple[str | None, str | None]] | None = None,
                  own_names: Collection[str] = (),
                  own_loops: Collection[str] = (),
                  _depth: int = 0) -> ActionPlan:
    """Return the validated plan. An empty plan means the turn produced nothing usable.

    `own_names` / `own_expand` (mcu_worldmodel/own.py, `--own`): a procedure name that is
    not a built-in but one of the model's own scripts is run through `own_expand`, and
    the plan text it returns is parsed HERE with the same caps, the remaining tick room
    as its step cap, and `_depth` 1 -- an own procedure cannot call another. Its notes
    come back prefixed with its name; it is one kept entry (`own: True`) worth as many
    queue items as its plan produced, so the executor and the log see it as one call.

    The caps are large because they have to be: these episodes run 12,000 steps or
    more, and a 40-step ceiling would mean 300 model turns for the diamond task before
    any thinking time at all. A single
    `strip_mine` procedure is worth ~100 ticks on its own.

    `entry_cap` is 40 rather than 20 because an absolute cursor makes a whole recipe one
    plan: opening a screen, picking up a stack, right-clicking it into six cells, putting
    the remainder back, taking the output and closing costs ~21 entries. At 20 the plan
    would be truncated exactly halfway through a craft -- with the ingredients in the grid
    and the screen still open, which is the most expensive state to be left in.

    `cursor` is a *projection* of the harness's `CursorState`, advanced as the plan is
    parsed so that an absolute cursor address late in a plan is computed from where the
    earlier entries will have left the cursor. Raw entries advance it too: a plan that
    hand-rolls a `camera` delta and then calls `cursor_to_slot` would otherwise address
    the slot from a stale position, which is exactly the drift the absolute form exists
    to remove.
    """
    notes: list[str] = []
    try:
        obj = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning(f"[actions] actions.json malformed: {exc}")
        return ActionPlan([], [], [f"actions.json did not parse: {exc}"])

    entries = obj.get("actions") if isinstance(obj, dict) else obj
    if not isinstance(entries, list):
        return ActionPlan([], [], ["expected a list under key 'actions'"])

    kept: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    # Budget in *ticks*, not list entries: a closed-loop marker (`_servo`, `_chop`) is one
    # queue entry that the runner resolves over up to `_cost` ticks, so it is charged its
    # worst case here. Charging it as 1 would let a plan of markers run several times the
    # step cap before the agent looks again.
    used = 0
    for entry in entries[:entry_cap]:
        if not isinstance(entry, dict):
            notes.append(f"skipped non-object entry: {entry!r}")
            continue
        room = step_cap - used
        if room <= 0:
            notes.append(f"step cap {step_cap} reached; remaining entries dropped")
            break

        if "procedure" in entry:
            name = str(entry["procedure"])
            overrides = _overrides(entry)      # lifts `why`/`leave_table` out of args
            args = entry.get("args") or {}
            if not isinstance(args, dict):
                notes.append(f"`args` for {name!r} must be an object; ignored")
                args = {}
            if name not in P.REGISTRY and name in own_names:
                if _depth > 0:
                    notes.append(f"{name}: an own procedure cannot call another own "
                                 f"procedure; `{name}` skipped")
                    continue
                if own_expand is None:
                    notes.append(f"{name}: own procedures are not enabled this run")
                    continue
                if name in own_loops:
                    # A closed loop (own.py, `own_live`): not expanded here. One marker
                    # the runner resolves from the tick its entry starts, charged its
                    # whole budget like every other closed-loop marker.
                    from mcu_worldmodel.own import LOOP_BUDGET
                    try:
                        want = max(1, int(args.get("ticks", LOOP_BUDGET)))
                    except (TypeError, ValueError):
                        want = LOOP_BUDGET
                    budget = min(want, room)
                    if budget < want:
                        notes.append(f"{name}: its loop shrunk to fit the step cap: {want} -> "
                                     f"{budget} ticks (the plan's {step_cap}-tick budget; call "
                                     f"it again to continue)")
                    kept.append({"procedure": name, "args": args, "steps": budget,
                                 "items": 1, "own": True, "loop": True, **overrides})
                    steps.append({"_ownloop": {"name": name, "args": dict(args),
                                               "budget": budget}, "_cost": budget})
                    used += budget
                    continue
                text, err = own_expand(name, dict(args))
                if err:
                    notes.append(f"{name} (mine/procedures/{name}.py) FAILED, nothing ran: "
                                 f"{err}")
                    continue
                sub = parse_actions(text or "", entry_cap=entry_cap, repeat_cap=repeat_cap,
                                    step_cap=room, allow_optional=allow_optional, info=info,
                                    cursor=cursor, own_expand=None, own_names=own_names,
                                    _depth=1)
                notes.extend(f"{name}: {n}" for n in sub.notes)
                if not sub.steps:
                    notes.append(f"{name}: its plan had nothing to run")
                    continue
                cost = sum(max(0, int(x.get("_cost", 1))) for x in sub.steps)
                # `atoms`: the built-ins the script's plan ran, in order, with their
                # queue items -- what lets a reflex see the atom running INSIDE the
                # call (agent._own_reflex_state), not just the script's name.
                atoms = [[e.get("procedure", "raw"),
                          e.get("items", e["steps"]) if "procedure" in e else e["repeat"]]
                         for e in sub.entries]
                kept.append({"procedure": name, "args": args, "steps": cost,
                             "items": len(sub.steps), "own": True, "atoms": atoms,
                             **overrides})
                steps.extend(sub.steps)
                used += cost
                continue
            expanded, note = P.expand(name, info=info, cursor=cursor, **args)
            if (not expanded and note and kept and name in P.DEFERRABLE
                    and "bad arguments" not in note):
                # Refused against the state NOW, but earlier entries of this plan run
                # first and may supply what is missing (logs from a harvest, the table
                # screen from use_until_gui). Queue it to expand when its turn comes.
                expanded = [{"_later": {"name": name, "args": dict(args), "why": note},
                             "_cost": 1}]
                note = (f"{name} will expand when its turn comes, after the entries "
                        f"before it; as things stand it would be refused: {note}")
            if note:
                # A procedure's own note -- "cannot craft stone_pickaxe: need 3x
                # cobblestone, have 1" -- is the most useful thing the turn produces when
                # it produces nothing else, so it reaches the log either way.
                notes.append(note)
            if not expanded:
                continue
            cut: list[dict[str, Any]] = []
            cost = 0
            for s in expanded:
                c = max(0, int(s.get("_cost", 1)))
                if cost + c > room:
                    shrunk = P.shrink_marker(s, room - cost)
                    if shrunk is not None:
                        cut.append(shrunk)
                        cost += int(shrunk["_cost"])
                        notes.append(f"procedure {name!r} shrunk to fit the step cap: "
                                     f"{c} -> {shrunk['_cost']} ticks (the plan's "
                                     f"{step_cap}-tick budget; call it again to continue)")
                    elif name in P.RESUMABLE and cut:
                        # A build that resumes (a filled cell is skipped next call) keeps
                        # what fits: build_portal_frame's 870 ticks were meant to run as
                        # two calls, and the all-or-nothing rule below dropped it whole
                        # (a staged scene: "NOT STARTED: it needs 870 ticks").
                        need = sum(max(0, int(x.get("_cost", 1))) for x in expanded)
                        notes.append(f"procedure {name!r} cut at the step cap after "
                                     f"{cost} of its {need} ticks; call it again from the "
                                     f"same spot to continue")
                    else:
                        # A macro that cannot shrink is all or nothing: a craft cut
                        # after its first clicks fills cells and never takes the output
                        # (one run: "craft(diamond_pickaxe) -> 1 ticks",
                        # then 400 steps of manual clicking). Drop the whole procedure
                        # and say so; it comes first next turn.
                        need = sum(max(0, int(x.get("_cost", 1))) for x in expanded)
                        notes.append(f"procedure {name!r} NOT STARTED: it needs {need} "
                                     f"ticks and only {room} of the plan's {step_cap}-tick "
                                     f"budget were left; put it first next turn")
                        cut = []
                    break
                cut.append(s)
                cost += c
            if not cut:
                continue
            # `steps` is the tick budget (what describe_entry reports); `items` is how
            # many queue entries were actually appended -- a closed-loop marker is one
            # item worth many ticks, and the runner's (action, entry) pairing walks items.
            kept.append({"procedure": name, "args": args, "steps": cost,
                         "items": len(cut), **overrides})
            steps.extend(cut)
            used += cost
            continue

        if not isinstance(entry.get("action"), dict):
            notes.append(f"entry has neither `procedure` nor `action`: {entry!r}")
            continue
        try:
            rep = max(1, min(repeat_cap, int(entry.get("repeat", 1))))
        except (TypeError, ValueError):
            notes.append(f"non-numeric repeat in {entry!r}; using 1")
            rep = 1
        action = _clean_action(entry["action"], notes, allow_optional)
        if action is None:
            continue
        if rep > room:
            notes.append(f"repeat {rep} truncated to {room} by the step cap")
            rep = room
        kept.append({"action": dict(entry["action"]), "repeat": rep, **_overrides(entry)})
        raw_steps = [dict(action) for _ in range(rep)]
        if cursor is not None:
            for s in raw_steps:
                cursor.apply(s)
        steps.extend(raw_steps)
        used += rep

    if len(entries) > entry_cap:
        notes.append(f"{len(entries)} entries submitted; only the first {entry_cap} ran")
    for n in notes:
        logger.warning(f"[actions] {n}")
    return ActionPlan(kept, steps, notes)


def describe_entry(entry: dict[str, Any]) -> str:
    """Compact rendering for the log -- only what the agent actually set."""
    if "procedure" in entry:
        args = ",".join(f"{k}={v}" for k, v in (entry.get("args") or {}).items())
        return f"[ACTION] {entry['procedure']}({args}) -> {entry['steps']} ticks"
    act = {k: v for k, v in entry["action"].items()
           if v not in (0, [0, 0], [0.0, 0.0])}
    return f"[ACTION] {json.dumps(act, separators=(',', ':'))} x{entry['repeat']}"
