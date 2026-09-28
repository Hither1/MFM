"""The OpenRouter Decisions client: JEV answers typed questions, not text.

    POST <base>/alpha/decisions
    {"model": "typesafe/jev-1.13",
     "state": {...},                       # string | object | array
     "questions": {"<name>": {"type": "choice", "instructions": "...",
                              "criteria": {"<key>": "<what this option means>"}}},
     "session_id": "<arm>"}                # <=256 chars, groups a run's decisions

    -> {"model": "...", "answers": {"<name>": {"type": "choice", "choice": "<key>",
                                               "confidence": 0.75,
                                               "probabilities": {...}}},
        "usage": {"input_tokens": N, "output_tokens": N, "cost": USD}}

`noul` answers carry a probability under "noul"; `score` answers a position under
"score" with a "legend". Schema read from OpenRouter's alpha reference, 2026-09-27.

stdlib only (urllib): the chassis runs inside the arm's venv on a compute node and no
arm may grow a dependency. The key never enters a log line or the process environment
of anything but this client -- `api_key` is read once from OPENROUTER_API_KEY or from
the launcher's key file (MCU_OPENROUTER_ENV, default ~/.codex-eval/openrouter.env, the
`OPENROUTER_API_KEY=` line) and is only ever an Authorization header.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# Two routes to the same model, and they are NOT interchangeable in their spelling:
#
#   openrouter  POST https://openrouter.ai/api/alpha/decisions, model `typesafe/jev-1.13`,
#               billed to the OpenRouter workspace, 32k context on its card.
#   typesafe    POST https://api.typesafe.ai/v1/systemone, model `jev-1.13.0` (bare, with
#               the aliases `jev-latest`/`jev-preview`), billed by TypeSafe directly, 64k
#               per request but 32k for the state plus the longest question, 1,200 RPM,
#               $0.042/MTok input with output free.
#
# The request and response bodies are the same shape on both (OpenRouter forwards to
# TypeSafe, one provider). A run pins a version either way, so a mid-wave model change
# cannot be mistaken for a method effect.
PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api",
        "path": "/alpha/decisions",
        "model": "typesafe/jev-1.13",
        "env": ("OPENROUTER_API_KEY",),
        "key_file_env": "MCU_OPENROUTER_ENV",
        "key_file": Path.home() / ".codex-eval" / "openrouter.env",
        "key_line": "OPENROUTER_API_KEY",
    },
    "typesafe": {
        "base_url": "https://api.typesafe.ai",
        "path": "/v1/systemone",
        "model": "jev-1.13.0",
        "env": ("JEV_API_KEY", "TYPESAFE_API_KEY"),
        "key_file_env": "MCU_JEV_ENV",
        "key_file": Path.home() / ".codex-eval" / "jev.env",
        "key_line": "JEV_API_KEY",
    },
}
#: Tried in this order when no provider is named: the first one whose key resolves wins.
PROVIDER_ORDER = ("typesafe", "openrouter")
DEFAULT_MODEL = PROVIDERS["openrouter"]["model"]
DEFAULT_BASE_URL = PROVIDERS["openrouter"]["base_url"]
#: Upstream races two requests with a 3 s timeout each; one call with a real ceiling is
#: the same thing without the doubled spend, and a chassis tick is not latency-bound.
DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRIES = 3
#: The launcher's key file (scripts/launch_g4_fasrc.sh KEYFILE). No user path in tree.
DEFAULT_KEY_FILE = PROVIDERS["openrouter"]["key_file"]
#: TypeSafe's cap is 32k tokens for the state plus the longest question. Budgeted in
#: characters at the conventional ~4 per token, with room for the questions: a state that
#: outgrows it is trimmed (`_fit_state`) rather than sent to be refused mid-run.
MAX_STATE_CHARS = 100_000
#: Trimmed in this order, biggest-cost-first, until the state fits.
TRIM_ORDER = ("recent_outcomes", "map_from_own_positions", "milestones_detail",
              "harness_notes", "inventory")
#: A criteria description longer than this is truncated: the menu is up to ~40 options
#: and the whole question has to stay small enough to answer inside a tick.
MAX_CRITERION_CHARS = 240


class DecisionError(RuntimeError):
    """The decisions endpoint could not be asked, or did not answer usefully."""


class DecisionsBudgetExceeded(DecisionError):
    """The account cannot spend. Retrying is pointless and the arm must not step blind.

    Measured 2026-09-27: this workspace's OpenRouter lifetime budget is exhausted
    ($5001.69 of $5000), so every call is `403 Workspace lifetime budget ... exceeded`.
    The `openrouter-budget-exhausted` note of 2026-09-12 is the same wall, and the arms
    that hit it kept stepping as no-ops for hours; the bridge ends the episode instead.
    """


@dataclass
class Question:
    """One typed question. `kind` is the endpoint's discriminator."""
    kind: str                                   # "choice" | "noul" | "score"
    instructions: str
    criteria: Any

    def payload(self) -> dict[str, Any]:
        return {"type": self.kind, "instructions": self.instructions,
                "criteria": self.criteria}


def choice(instructions: str, criteria: dict[str, str]) -> Question:
    """Pick one key. `criteria` maps the option key to what choosing it means."""
    if not criteria:
        raise ValueError("a choice question needs at least one option")
    trimmed = {k: _trim(v) for k, v in criteria.items()}
    return Question("choice", instructions, trimmed)


def noul(instructions: str, when_true: str, when_false: str) -> Question:
    """A probability that a condition holds."""
    return Question("noul", instructions,
                    {"true": _trim(when_true), "false": _trim(when_false)})


def score(instructions: str, levels: list[str]) -> Question:
    """A position on an ordered scale, low to high."""
    if not levels:
        raise ValueError("a score question needs at least one level")
    return Question("score", instructions, [_trim(x) for x in levels])


def _trim(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_CRITERION_CHARS else text[:MAX_CRITERION_CHARS - 1] + "…"


@dataclass
class Answer:
    kind: str
    value: Any                                  # the chosen key / probability / position
    confidence: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    legend: dict[str, str] = field(default_factory=dict)

    @property
    def is_true(self) -> bool:
        """For a `noul`: did it come out above even odds?"""
        return self.kind == "noul" and float(self.value or 0.0) >= 0.5


@dataclass
class Decision:
    answers: dict[str, Answer]
    model: str = ""
    request_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: int = 0

    def get(self, name: str) -> Answer | None:
        return self.answers.get(name)


class JevDecider:
    """One HTTP client for the decisions endpoint, plus this run's usage tally."""

    def __init__(self, *, provider: str | None = None, model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 key_file: str | Path | None = None, timeout: float = DEFAULT_TIMEOUT,
                 retries: int = DEFAULT_RETRIES, session_id: str = "",
                 max_state_chars: int = MAX_STATE_CHARS) -> None:
        """`provider` is "typesafe" (TypeSafe's own API) or "openrouter" (the resale
        route). None picks the first in `PROVIDER_ORDER` whose key resolves, so an arm
        launched with a Jev key uses it and falls back to OpenRouter without a flag."""
        if provider is None and api_key is None and key_file is None:
            provider = _first_provider_with_a_key()
        elif provider is None:
            provider = "openrouter"             # an explicit key is the resale route's
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}: {sorted(PROVIDERS)}")
        spec = PROVIDERS[provider]
        self.provider = provider
        self.path = str(spec["path"])
        self.model = model or str(spec["model"])
        self.base_url = (base_url or str(spec["base_url"])).rstrip("/")
        self.timeout = float(timeout)
        self.retries = max(1, int(retries))
        self.session_id = session_id[:256]
        self.max_state_chars = int(max_state_chars)
        self.states_trimmed = 0
        self._key = api_key or read_api_key(key_file, provider=provider)
        self.calls = 0
        self.failures = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.latency_ms = 0

    # -- the one call ------------------------------------------------------------------

    def decide(self, state: Any, questions: dict[str, Question]) -> Decision:
        """Ask every question about one state. Raises `DecisionError` on failure."""
        if not questions:
            raise ValueError("decide() needs at least one question")
        payload = {name: q.payload() for name, q in questions.items()}
        state, trimmed = _fit_state(state, payload, self.max_state_chars)
        if trimmed:
            self.states_trimmed += 1
            logger.debug(f"[jev] state trimmed to fit: dropped {trimmed}")
        body: dict[str, Any] = {"model": self.model, "state": state, "questions": payload}
        if self.session_id and self.provider == "openrouter":
            # `session_id` groups a run's decisions on OpenRouter's side. TypeSafe's
            # first-party body does not document it, so it is not sent there.
            body["session_id"] = self.session_id
        raw, latency_ms = self._post(self.path, body)
        decision = _parse_decision(raw, questions)
        decision.latency_ms = latency_ms
        self.calls += 1
        self.input_tokens += decision.input_tokens
        self.output_tokens += decision.output_tokens
        self.cost += decision.cost
        self.latency_ms += latency_ms
        return decision

    def audit(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "calls": self.calls,
                "failures": self.failures, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cost_usd": round(self.cost, 6),
                "states_trimmed": self.states_trimmed,
                "mean_latency_ms": round(self.latency_ms / self.calls) if self.calls else 0}

    # -- transport ---------------------------------------------------------------------

    def _post(self, path: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
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
                return payload, int((time.monotonic() - started) * 1000)
            except urllib.error.HTTPError as exc:
                detail = _error_detail(exc)
                if exc.code in (402, 403) and "budget" in detail.lower():
                    self.failures += 1
                    raise DecisionsBudgetExceeded(detail) from exc
                last = DecisionError(f"decisions HTTP {exc.code}: {detail}")
                if exc.code in (400, 401, 403, 404, 422):
                    break                        # a bad request will stay bad
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last = DecisionError(f"decisions call failed: {exc!r}")
            if attempt + 1 < self.retries:
                time.sleep(min(2.0 * (attempt + 1), 5.0))
        self.failures += 1
        assert last is not None
        logger.warning(f"[jev] {last}")
        raise last


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return exc.reason if isinstance(exc.reason, str) else str(exc)
    err = payload.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err or payload)


def _parse_decision(raw: dict[str, Any], asked: dict[str, Question]) -> Decision:
    answers_raw = raw.get("answers")
    if not isinstance(answers_raw, dict):
        raise DecisionError(f"no answers in the response: {str(raw)[:300]}")
    answers: dict[str, Answer] = {}
    for name, ans in answers_raw.items():
        if not isinstance(ans, dict):
            continue
        kind = str(ans.get("type") or (asked[name].kind if name in asked else ""))
        if kind == "choice":
            value: Any = ans.get("choice")
        elif kind == "noul":
            value = ans.get("noul")
        elif kind == "score":
            value = ans.get("score")
        else:
            continue
        answers[name] = Answer(
            kind=kind, value=value,
            confidence=_as_float(ans.get("confidence")),
            probabilities={str(k): float(v) for k, v in (ans.get("probabilities") or {}).items()
                           if _as_float(v) is not None},
            legend={str(k): str(v) for k, v in (ans.get("legend") or {}).items()})
    if not answers:
        raise DecisionError(f"the response answered none of {sorted(asked)}")
    usage = raw.get("usage") or {}
    return Decision(answers=answers, model=str(raw.get("model") or ""),
                    request_id=str(raw.get("id") or ""),
                    input_tokens=int(usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    cost=float(usage.get("cost") or 0.0))


def _as_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def find_api_key(key_file: str | Path | None = None, *, provider: str = "openrouter"
                 ) -> tuple[str, Path]:
    """This provider's key from its environment variables or its key file, and where the
    file was looked for. Never logged, never echoed, never put in any process's
    environment -- the caller turns it into one Authorization header."""
    spec = PROVIDERS[provider]
    for var in spec["env"]:
        val = os.environ.get(var, "").strip()
        if val:
            return val, Path(str(spec["key_file"]))
    path = Path(key_file or os.environ.get(str(spec["key_file_env"]))
                or str(spec["key_file"]))
    prefix = f"{spec['key_line']}="
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix):
                key = line.split("=", 1)[1].strip()
                if key:
                    return key, path
    except OSError:
        pass
    return "", path


def _first_provider_with_a_key() -> str:
    for provider in PROVIDER_ORDER:
        key, _ = find_api_key(provider=provider)
        if key:
            return provider
    return PROVIDER_ORDER[-1]


def read_api_key(key_file: str | Path | None = None, *, provider: str = "openrouter") -> str:
    key, path = find_api_key(key_file, provider=provider)
    if key:
        return key
    spec = PROVIDERS[provider]
    raise DecisionError(
        f"no {provider} key for JEV: set {' or '.join(spec['env'])}, or put a "
        f"{spec['key_line']}= line in {path} ({spec['key_file_env']}). JEV is served by "
        "TypeSafe and resold by OpenRouter; there is no codex or Claude route for it.")


def _fit_state(state: Any, questions: dict[str, Any], budget: int) -> tuple[Any, list[str]]:
    """Cut the state down to the provider's state-plus-question ceiling.

    TypeSafe refuses a request over 32k tokens of state plus longest question, and a
    long-running arm grows exactly the fields that would cross it -- the outcome ring,
    the [MAP] block, the milestone detail. Trimmed here, in `TRIM_ORDER`, so a decision
    is degraded rather than lost mid-run; the caller counts how often it happened.
    """
    room = budget - len(json.dumps(questions, default=str))
    if not isinstance(state, dict) or len(json.dumps(state, default=str)) <= room:
        return state, []
    out, dropped = dict(state), []
    for field in TRIM_ORDER:
        if field not in out:
            continue
        value = out[field]
        if isinstance(value, list) and len(value) > 1:
            out[field] = value[-1:]              # keep the most recent
        else:
            out.pop(field)
        dropped.append(field)
        if len(json.dumps(out, default=str)) <= room:
            return out, dropped
    text = json.dumps(out, default=str)
    if len(text) > room:
        return {"truncated_state": text[:max(0, room - 32)]}, dropped + ["everything else"]
    return out, dropped
