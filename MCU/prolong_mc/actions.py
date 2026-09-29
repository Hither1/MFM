"""Parse and validate the `actions.json` a PRO-LONG turn produces.

Mirrors `BaseAgent._parse_actions_json_text` in shape -- accept `{"actions": [...]}`
or a bare list, cap the length, skip and warn on anything unrecognised -- but the
entries are MineExplorer action dicts with a `repeat` count instead of ARC's
ACTION1-7 strings.

The action vocabulary and validation rules are the baseline's: keys are the wire
spelling from `mc_agent/context.py`'s prompt, and `DefaultActionSpace.validate_action`
and `.dump_action_to_dict` decide what is legal and what goes on the wire. The key
mapping is repeated here rather than reusing `DefaultActionSpace.load_action` for two
reasons: its dict branch references `action_content` before assignment, so only the
string path runs; and on a validation failure it silently substitutes a no-op, which
would turn an agent mistake into an invisible wasted step instead of a logged one.
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from mc_agent.action_space import ActionState, DefaultActionSpace

# Wire key -> ActionState field. Exactly the keys the prompt advertises.
_SIMPLE_KEYS = {
    "ESC": "ESC", "attack": "attack", "back": "back", "drop": "drop",
    "forward": "forward", "inventory": "inventory", "jump": "jump",
    "left": "left", "right": "right", "sneak": "sneak", "sprint": "sprint",
    "use": "use", "pickItem": "pick_item", "swapHands": "swap_hands",
}


class ActionPlan:
    """One validated plan: the entries as given, and the flat env-action sequence.

    `subgoal` and `recommit` are the plan's other two fields when the goal-review layer
    is on (`prolong_mc.goals`). They are parsed unconditionally and ignored when it is
    off, so the parser has one shape and the arms differ only in whether the runner
    meters what the agent wrote.
    """

    def __init__(self, entries: list[dict[str, Any]], steps: list[dict[str, Any]],
                 subgoal: str = "", recommit: str = ""):
        self.entries = entries
        self.steps = steps
        self.subgoal = subgoal
        self.recommit = recommit

    def __len__(self) -> int:
        return len(self.steps)

    def __bool__(self) -> bool:
        return bool(self.steps)


def _to_action_state(raw: dict[str, Any]) -> ActionState | None:
    state = ActionState()
    for key, value in raw.items():
        if key in _SIMPLE_KEYS:
            setattr(state, _SIMPLE_KEYS[key], int(value))
        elif key == "camera":
            state.camera = [float(value[0]), float(value[1])]
        elif key.startswith("hotbar."):
            idx = int(key.split(".", 1)[1])
            if not 1 <= idx <= 9:
                logger.warning(f"[actions] hotbar index out of range: {key}")
                return None
            hotbars = list(state.hotbars)
            hotbars[idx - 1] = int(value)
            state.hotbars = hotbars
        else:
            logger.warning(f"[actions] unknown action key, ignoring: {key!r}")
    return state


def parse_actions(
    raw_text: str,
    *,
    action_cap: int = 15,
    repeat_cap: int = 20,
    step_cap: int = 40,
) -> ActionPlan:
    """Return the validated plan. An empty plan means the turn produced nothing usable."""
    space = DefaultActionSpace()
    try:
        obj = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning(f"[actions] actions.json malformed: {exc}")
        return ActionPlan([], [])

    entries = obj.get("actions") if isinstance(obj, dict) else obj
    subgoal = str(obj.get("subgoal") or "").strip() if isinstance(obj, dict) else ""
    recommit = str(obj.get("recommit") or "").strip() if isinstance(obj, dict) else ""
    if not isinstance(entries, list):
        logger.warning(
            f"[actions] expected a list under 'actions', got {type(entries).__name__}"
        )
        return ActionPlan([], [])

    kept: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    for entry in entries[:action_cap]:
        if not isinstance(entry, dict) or not isinstance(entry.get("action"), dict):
            logger.warning(f"[actions] skipping unrecognised entry: {entry!r}")
            continue

        try:
            repeat = int(entry.get("repeat", 1))
        except (TypeError, ValueError):
            logger.warning(f"[actions] non-numeric repeat, skipping entry: {entry!r}")
            continue
        repeat = max(1, min(repeat_cap, repeat))

        try:
            state = _to_action_state(entry["action"])
        except (TypeError, ValueError, IndexError) as exc:
            logger.warning(f"[actions] bad action dict ({exc}), skipping: {entry!r}")
            continue
        if state is None or not space.validate_action(state):
            logger.warning(f"[actions] validation failed, skipping entry: {entry!r}")
            continue

        wire = space.dump_action_to_dict(state)
        room = step_cap - len(steps)
        if room <= 0:
            logger.warning(
                f"[actions] step cap {step_cap} reached; dropping remaining entries"
            )
            break
        if repeat > room:
            logger.warning(
                f"[actions] truncating repeat {repeat} -> {room} to respect the step cap"
            )
            repeat = room

        kept.append({"action": dict(entry["action"]), "repeat": repeat})
        steps.extend(dict(wire) for _ in range(repeat))

    if len(entries) > action_cap:
        logger.warning(
            f"[actions] {len(entries)} entries submitted; only the first {action_cap} are executed"
        )
    return ActionPlan(kept, steps, subgoal=subgoal, recommit=recommit)


def describe_entry(entry: dict[str, Any]) -> str:
    """Compact rendering for the log: only the keys the agent actually set."""
    act = {k: v for k, v in entry["action"].items() if v not in (0, [0, 0], [0.0, 0.0])}
    return f"{json.dumps(act, separators=(',', ':'))} x{entry['repeat']}"
