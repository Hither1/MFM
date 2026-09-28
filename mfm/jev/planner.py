"""Astra as the planner: consulted on a trigger, answering with one objective.

Upstream (`rmalde/minecraft-agent`) calls its plan model on the chat-completions API and
prints the returned object as PLAN; the selector then chooses actions under it until a
trigger fires again. Here the same call is `POST <base>/v1/chat/completions` with a
`json_schema` response format, so the plan arrives as a typed object rather than prose
the bridge would have to guess at (`gpt-6-astra` and `gpt-5.6-sol` both list
`structured_outputs` on OpenRouter).

The plan is advice, not an actuator: nothing the planner says reaches the game except by
narrowing the menu JEV picks from (`mfm/jev/menu.py`), and a waypoint it invents is still
routed over cells the runner has walked. That is what keeps the arm inside the parity
lane -- the planner cannot name a coordinate the harness would not let any other arm's
`go_to` target.

stdlib only, and the key is read the same way as the decisions client's.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

import os

from mfm.jev.decisions import DEFAULT_BASE_URL, DecisionError, read_api_key

# The planner's two routes. Upstream reaches Astra through OpenRouter; with the selector
# on TypeSafe's own API (a Jev key), OpenRouter may have nothing left to spend, and the
# planner can go straight to OpenAI instead -- which is the same model, a different bill,
# and a bare model id (`gpt-6-astra`, not `openai/gpt-6-astra`).
PLANNER_PROVIDERS: dict[str, dict[str, object]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api", "model": "openai/gpt-6-astra",
                   "env": ("OPENROUTER_API_KEY",), "key_provider": "openrouter"},
    "openai": {"base_url": "https://api.openai.com", "model": "gpt-6-astra",
               "env": ("OPENAI_API_KEY",), "key_provider": ""},
}
#: Tried in this order when no provider is named: the first whose key is present.
PLANNER_ORDER = ("openai", "openrouter")
#: Upstream's default planner (`PLANNER_MODEL=openai/gpt-6-astra`); `gpt-5.6-sol` is its
#: documented alternative and this ladder's other planner model.
DEFAULT_MODEL = "openai/gpt-6-astra"
DEFAULT_EFFORT = "high"
#: A re-plan is allowed to cost what one logbook turn costs (run-arm.sh --step-timeout is
#: 600 s and the chassis gives a codex turn 480).
DEFAULT_TIMEOUT = 300.0
DEFAULT_RETRIES = 2

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["objective", "targets", "waypoint", "avoid", "reasoning"],
    "properties": {
        "objective": {"type": "string", "maxLength": 240,
                      "description": "One sentence: what to accomplish next, in terms of "
                                     "the task's milestones."},
        "targets": {"type": "array", "maxItems": 6, "items": {"type": "string"},
                    "description": "Item ids to obtain or craft under this objective, "
                                   "most urgent first."},
        "waypoint": {"type": ["object", "null"], "additionalProperties": False,
                     "required": ["x", "y", "z", "why"],
                     "properties": {"x": {"type": "number"}, "y": {"type": "number"},
                                    "z": {"type": "number"},
                                    "why": {"type": "string", "maxLength": 120}},
                     "description": "Where to be, or null. Only a coordinate the state "
                                    "block or the [MAP] names -- never a guess."},
        "avoid": {"type": "array", "maxItems": 6, "items": {"type": "string"},
                  "description": "Action keys from the menu not to take under this "
                                 "objective, and hazards to keep away from."},
        "reasoning": {"type": "string", "maxLength": 600,
                      "description": "Why this objective now, from the state and the "
                                     "record. This is the [PLAN] the log keeps."},
    },
}

SYSTEM_PROMPT = (
    "You are the PLANNER for an agent playing Minecraft. You are called only when "
    "something changed: there is no plan, the waypoint was reached, the selector found "
    "nothing worth doing, or actions keep failing. You do not act. You set ONE objective, "
    "and a fast decision model chooses each bounded action under it until you are called "
    "again.\n\n"
    "You see exactly what a human player at the keyboard would: the current view, your "
    "position, vitals and inventory, the task's milestones, what the runner has itself "
    "walked and seen ([MAP]), the last entries' outcomes and the harness's notes. There "
    "is no block data, no world seed and no entity tracker: a coordinate you did not read "
    "off the state block or the [MAP] is a guess, and a guessed waypoint costs the run "
    "hundreds of steps. Say `null` instead.\n\n"
    "Judge from the record, not from hope. If the last objective was not reached, say why "
    "in `reasoning` and change the approach rather than restating it. Prefer the milestone "
    "that is one action away over the one that is ten."
)


@dataclass
class Plan:
    objective: str = ""
    targets: list[str] = field(default_factory=list)
    waypoint: dict[str, Any] | None = None
    avoid: list[str] = field(default_factory=list)
    reasoning: str = ""
    #: Why the planner was called (`mfm/jev/session.py` Trigger), for the log and audit.
    trigger: str = ""
    step: int = 0

    def line(self) -> str:
        """The one-line form the state block shows JEV."""
        bits = [self.objective or "(none)"]
        if self.targets:
            bits.append("targets: " + ", ".join(self.targets))
        if self.waypoint:
            w = self.waypoint
            bits.append(f"waypoint: ({w.get('x')}, {w.get('y')}, {w.get('z')})"
                        + (f" -- {w['why']}" if w.get("why") else ""))
        if self.avoid:
            bits.append("avoid: " + ", ".join(self.avoid))
        return " | ".join(bits)

    def briefing(self) -> str:
        """What the chassis writes as this entry's [PLAN] section."""
        head = f"[OBJECTIVE] {self.objective}" if self.objective else "[OBJECTIVE] (none)"
        why = f"\n{self.reasoning}" if self.reasoning else ""
        return f"{head} (planner trigger: {self.trigger}){why}"


class PlannerError(RuntimeError):
    pass


class AstraPlanner:
    def __init__(self, *, provider: str | None = None, model: str | None = None,
                 effort: str = DEFAULT_EFFORT, base_url: str | None = None,
                 api_key: str | None = None, key_file: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES,
                 max_images: int = 1) -> None:
        if provider is None:
            provider = _first_planner_with_a_key() if api_key is None else "openrouter"
        if provider not in PLANNER_PROVIDERS:
            raise PlannerError(f"unknown planner provider {provider!r}: "
                               f"{sorted(PLANNER_PROVIDERS)}")
        spec = PLANNER_PROVIDERS[provider]
        self.provider = provider
        # A model id is spelled for its route: `openai/gpt-6-astra` on OpenRouter, bare on
        # OpenAI's own API. The launcher passes the bare id, so fix it up here rather than
        # making every caller know which route it is on.
        self.model = _spell_model(model or str(spec["model"]), provider)
        self.effort = effort
        self.base_url = (base_url or str(spec["base_url"])).rstrip("/")
        self.timeout = float(timeout)
        self.retries = max(1, int(retries))
        self.max_images = max(0, int(max_images))
        try:
            self._key = api_key or _planner_key(provider, key_file)
        except DecisionError as exc:
            raise PlannerError(str(exc)) from exc
        self.calls = 0
        self.failures = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.images_sent = 0
        self.latency_ms = 0

    def plan(self, *, task: str, state: dict[str, Any], trigger: str,
             frame_png: bytes | None = None) -> Plan:
        """One planning turn. Raises `PlannerError` when no plan could be obtained."""
        content: list[dict[str, Any]] = [{"type": "text", "text": _user_text(task, state, trigger)}]
        if frame_png and self.max_images:
            url = "data:image/png;base64," + base64.b64encode(frame_png).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": url}})
        body = {
            "model": self.model,
            # `reasoning_effort` is accepted on both routes (OpenRouter lists it among
            # this model's supported parameters, and it is OpenAI's own spelling).
            "reasoning_effort": self.effort,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": content}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "plan", "strict": True,
                                                "schema": PLAN_SCHEMA}},
        }
        raw = self._post("/v1/chat/completions", body)
        if len(content) > 1:
            self.images_sent += 1
        plan = _parse_plan(raw)
        plan.trigger = trigger
        plan.step = int(state.get("step") or 0)
        return plan

    def audit(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "effort": self.effort,
                "calls": self.calls,
                "failures": self.failures, "images_sent": self.images_sent,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost, 6),
                "mean_latency_ms": round(self.latency_ms / self.calls) if self.calls else 0}

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        url = f"{self.base_url}{path}"
        last: Exception | None = None
        for attempt in range(self.retries):
            started = time.monotonic()
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
                "Connection": "close",
            })
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                self.calls += 1
                self.latency_ms += int((time.monotonic() - started) * 1000)
                usage = payload.get("usage") or {}
                self.input_tokens += int(usage.get("prompt_tokens") or 0)
                self.output_tokens += int(usage.get("completion_tokens") or 0)
                self.cost += float((usage.get("cost") if isinstance(usage.get("cost"), (int, float))
                                    else 0.0) or 0.0)
                return payload
            except urllib.error.HTTPError as exc:
                from mfm.jev.decisions import _error_detail
                detail = _error_detail(exc)
                last = PlannerError(f"planner HTTP {exc.code}: {detail}")
                if exc.code in (400, 401, 403, 404, 422):
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last = PlannerError(f"planner call failed: {exc!r}")
            if attempt + 1 < self.retries:
                time.sleep(2.0 * (attempt + 1))
        self.failures += 1
        assert last is not None
        logger.warning(f"[jev] {last}")
        raise last


def _user_text(task: str, state: dict[str, Any], trigger: str) -> str:
    return (f"TASK\n{task.strip()}\n\nWHY YOU WERE CALLED\n{trigger}\n\n"
            f"STATE\n{json.dumps(state, indent=1, default=str)}\n\n"
            "Answer with the plan object. One objective, reachable from here.")


def _parse_plan(raw: dict[str, Any]) -> Plan:
    choices = raw.get("choices") or []
    if not choices:
        raise PlannerError(f"the planner returned no choices: {str(raw)[:300]}")
    message = (choices[0] or {}).get("message") or {}
    text = message.get("content")
    if isinstance(text, list):                   # some providers chunk the content
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    if not isinstance(text, str) or not text.strip():
        refusal = message.get("refusal")
        raise PlannerError(f"the planner returned no content{f': {refusal}' if refusal else ''}")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerError(f"the plan did not parse as JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise PlannerError("the plan was not an object")
    waypoint = obj.get("waypoint")
    if not isinstance(waypoint, dict):
        waypoint = None
    elif not all(isinstance(waypoint.get(k), (int, float)) for k in ("x", "y", "z")):
        waypoint = None
    return Plan(objective=str(obj.get("objective") or "").strip(),
                targets=[str(x) for x in (obj.get("targets") or []) if str(x).strip()][:6],
                waypoint=waypoint,
                avoid=[str(x) for x in (obj.get("avoid") or []) if str(x).strip()][:6],
                reasoning=str(obj.get("reasoning") or "").strip())


def _spell_model(model: str, provider: str) -> str:
    """`openai/gpt-6-astra` on OpenRouter, `gpt-6-astra` on OpenAI's own API."""
    if provider == "openai":
        return model.split("/", 1)[1] if model.startswith("openai/") else model
    if "/" not in model:
        return f"openai/{model}"
    return model


def _planner_key(provider: str, key_file: str | None) -> str:
    spec = PLANNER_PROVIDERS[provider]
    for var in spec["env"]:                      # type: ignore[union-attr]
        val = os.environ.get(str(var), "").strip()
        if val:
            return val
    if spec["key_provider"]:
        return read_api_key(key_file, provider=str(spec["key_provider"]))
    raise PlannerError(f"no planner key: set {' or '.join(spec['env'])}"  # type: ignore[arg-type]
                       f" for the {provider} route")


def _first_planner_with_a_key() -> str:
    for provider in PLANNER_ORDER:
        spec = PLANNER_PROVIDERS[provider]
        if any(os.environ.get(str(v), "").strip() for v in spec["env"]):  # type: ignore[union-attr]
            return provider
        if spec["key_provider"]:
            from mfm.jev.decisions import find_api_key
            key, _ = find_api_key(provider=str(spec["key_provider"]))
            if key:
                return provider
    return PLANNER_ORDER[-1]
