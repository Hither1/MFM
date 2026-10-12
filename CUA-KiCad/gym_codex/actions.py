"""The action contract every gym_codex arm shares: vocabulary, reference text, parser.

Factored out of ``codex_gui_agent.py`` so the mfm arm (``mfm_agent.py``) emits
exactly the same tool calls from exactly the same JSON shapes as the direct arm. The
arms differ in what the model remembers, not in what it may do -- an action the
direct arm would clamp, drop or refuse is clamped, dropped or refused identically
here, and the feedback text it reads next turn is the same string.

``parse_batch`` is pure: it takes the decoded JSON object (or None) and a tool-call
factory, and returns the calls, the done flag, the feedback to queue and the compact
line for the action log. The agents own the queueing and the log.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

# The action names the model may emit, mirroring LiteDesktopActionSet plus the finish
# tools. Kept as a literal so a typo'd model action fails HERE with feedback, not inside
# the env.
COORD_ACTIONS = {"click", "mouse_move", "drag", "scroll"}
ALLOWED_ACTIONS = COORD_ACTIONS | {
    "key", "key_down", "key_up", "hold_key", "type",
    "mouse_down", "mouse_up", "wait", "screenshot", "cursor_position",
}

#: Batches longer than this are truncated, not refused.
MAX_BATCH = 5

#: The coordinate convention and the action list, verbatim from the direct arm's system
#: prompt. The memory arm splices this into its own AGENTS.md so both arms read
#: one description of the action space.
ACTION_REFERENCE = """Coordinates are normalized to [0, 1000] on both axes: (0,0) is the top-left of the screen, (1000,1000) the bottom-right — always fractions of the screen times 1000, NEVER raw pixels.

Available actions (each an object in an "actions" list):
  {"action": "click", "coordinate": [x, y], "button": "left|right|middle", "clicks": 1|2|3}
  {"action": "mouse_move", "coordinate": [x, y]}
  {"action": "drag", "start_coordinate": [x, y], "coordinate": [x, y], "button": "left"}
  {"action": "scroll", "direction": "up|down|left|right", "amount": N, "coordinate": [x, y]}
  {"action": "type", "text": "...", "press_enter": false}      # types into the FOCUSED field
  {"action": "key", "keys": ["ctrl", "s"]}                     # press+release a combo
  {"action": "key_down", "keys": [...]} / {"action": "key_up", "keys": [...]}
  {"action": "hold_key", "keys": [...], "duration": seconds}
  {"action": "wait", "duration": seconds}
  {"action": "screenshot"}                                     # just look again"""

#: The terminate forms, likewise verbatim.
TERMINATE_REFERENCE = """To END the episode, reply instead with:
  {"terminate": {"status": "success"}}   # you believe the task is complete
  {"terminate": {"status": "failure", "reason": "..."}}   # you cannot complete it"""

#: The direct arm's general rules; the mfm arm restates them in its own prompt.
GENERAL_RULES = """General rules:
- Before typing into any app or field, verify in the CURRENT screenshot that the target window/field actually exists and is focused — text typed blind goes to whatever is active and is lost.
- Never batch input in the same turn that opens the app or dialog it targets; open, look, then act.
- After typing something long, check the screenshot that it appears complete before pressing enter.
The evaluator checks real system state at the end — files, settings, app state — so make the change durable (save files, confirm dialogs) before terminating."""


def clamp_coord(v: Any) -> list[int] | None:
    if (isinstance(v, (list, tuple)) and len(v) == 2
            and all(isinstance(c, (int, float)) for c in v)):
        return [max(0, min(1000, int(round(c)))) for c in v]
    return None


def last_json_block(reply: str) -> dict | None:
    """The model's one fenced json block, or the last parseable {...} as fallback."""
    fences = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", reply, re.DOTALL)
    candidates = fences or re.findall(r"\{.*\}", reply, re.DOTALL)
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def describe(a: dict) -> str:
    name = a["action"]
    if name == "type":
        return f'type("{a.get("text", "")[:60]}")'
    if name in ("key", "key_down", "key_up", "hold_key"):
        return f'{name}({"+".join(a.get("keys", []))})'
    if "coordinate" in a:
        return f'{name}({a["coordinate"][0]},{a["coordinate"][1]})'
    return name


@dataclass
class ParsedBatch:
    calls: list[dict]
    done: bool
    feedback: str | None
    log_line: str


#: What the model is told when its turn produced no JSON at all. The direct arm's
#: wording names the fenced block; the mfm arm names the artifact file.
NO_JSON_FEEDBACK = ("Your reply had no parseable JSON block; nothing was executed. "
                    "Reply with one ```json fenced block as instructed.")


def parse_batch(obj: dict | None, tool_call: Callable[[str, dict], dict],
                no_json_feedback: str = NO_JSON_FEEDBACK) -> ParsedBatch:
    """Turn the decoded reply into env tool calls, or a no-op with feedback.

    Behaviour is the direct arm's ``CodexGuiAgent._parse`` line for line: terminate
    and response end the episode; an empty ``actions`` list is terminate(success);
    unknown actions and bad coordinates are dropped with feedback; a click without a
    coordinate is dropped; batches are capped at ``MAX_BATCH``.
    """
    if obj is None:
        return ParsedBatch([], False, no_json_feedback, "(unparseable reply; no action executed)")

    if "terminate" in obj:
        t = obj["terminate"] if isinstance(obj["terminate"], dict) else {}
        status = t.get("status") if t.get("status") in ("success", "failure") else "success"
        args = {"status": status}
        if t.get("reason"):
            args["reason"] = str(t["reason"])[:500]
        return ParsedBatch([tool_call("terminate", args)], True, None, f"terminate({status})")
    if "response" in obj:
        text = obj["response"].get("text", "") if isinstance(obj["response"], dict) else str(obj["response"])
        return ParsedBatch([tool_call("response", {"text": text})], True, None, "response(...)")

    raw_actions = obj.get("actions")
    if isinstance(raw_actions, list) and not raw_actions:
        # An empty batch is the model saying "nothing left to do" — treat it as
        # terminate(success) rather than a no-op that burns the step budget
        # (measured: a completed task went unscored this way).
        return ParsedBatch([tool_call("terminate", {"status": "success"})], True, None,
                           "terminate(success, via empty actions)")
    if not isinstance(raw_actions, list):
        return ParsedBatch([], False,
                           'Your JSON had no "actions" list (and no terminate). Nothing was executed.',
                           "(JSON without actions; no action executed)")

    cleaned: list[dict] = []
    problems: list[str] = []
    for a in raw_actions[:MAX_BATCH]:                    # hard cap per batch
        if not isinstance(a, dict) or a.get("action") not in ALLOWED_ACTIONS:
            problems.append(f"unknown action {a!r}")
            continue
        a = dict(a)
        name = a.pop("action")
        for ck in ("coordinate", "start_coordinate"):
            if ck in a:
                cc = clamp_coord(a[ck])
                if cc is None:
                    a.pop(ck)
                    problems.append(f"{name}: bad {ck}, dropped")
                else:
                    a[ck] = cc
        if name == "click" and "coordinate" not in a:
            problems.append("click without coordinate dropped")
            continue
        cleaned.append({"action": name, **a})
    feedback = ("Some actions were invalid and skipped: " + "; ".join(problems)) if problems else None
    if not cleaned:
        return ParsedBatch([], False, feedback, "(all actions invalid; nothing executed)")
    return ParsedBatch([tool_call("computer", {"actions": cleaned})], False, feedback,
                       "; ".join(describe(a) for a in cleaned))
