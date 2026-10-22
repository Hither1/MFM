"""The turn protocol of a memory arm, with the benchmark as a subclass.

What every arm does, per environment step:

    observe(obs)   write the log section for this observation (and the action that
                   produced it), flush the plan queue if the benchmark says so
    act(obs)       if the queue is empty, publish the visible workspace and call the
                   model until it yields a plan (or the retry budget is spent), then
                   pop one queued item and hand it to the driver

What differs between benchmarks is expressed as hook methods the subclass implements:
how a section is rendered, what the turn prompt is, how the artifact parses into a
plan, when to flush, how failures are retried. The KiCad arm
(`CUA-KiCad/gym_codex/mfm_agent.py`) is such a subclass; it keeps the driver
interface its benchmark calls (`predict`) as a thin shim around `observe` / `act`. The
Minecraft harness has its own turn loop (`MCU/mcu_worldmodel/agent.py`).

Memory is written at fixed points: the log directly (its calls carry the rendered
lines), and every `MemorySink` in `self.sinks` through the hooks in
`mfm.memory.sink`. An arm with a second memory (the episode store) adds a sink; nothing
else changes.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from mfm.backend import errors
from mfm.memory.log import EpisodeLog
from mfm.memory.sink import MemorySink

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """One environment observation, as the protocol needs it.

    `step` is the environment's step index; `attachment` the log-relative path of the
    frame or screenshot saved for it (attached to the next model call); `state` and
    `raw` are the benchmark's, for its own hooks.
    """
    step: int
    attachment: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass
class Plan:
    """One model call's output, validated by the benchmark's `parse_plan`.

    `entries` are the plan's units as the benchmark defines them (an MCU
    `{"action", "repeat"}` entry, a KiCad batch); `ticks[i]` is how many environment
    steps entry i occupies; `steps` is the flat per-step payload sequence returned to
    the driver one at a time; `think` is the text written as the log's [PLAN] block and
    `briefing` the one-shot text before it.
    """
    entries: list[Any]
    ticks: list[int]
    steps: list[Any]
    think: str = ""
    briefing: str = ""
    extra: Any = None


class MemoryAgent:
    """The shared protocol. Subclass per benchmark; see the module docstring."""

    arm = "memory"
    #: "fixed": `analyzer_retries` attempts, a nudge after a failure, nothing else.
    #: "extend": refusals and capacity errors extend the budget with backoff and a
    #: transient infrastructure failure at the end is raised to the driver (the KiCad
    #: arm, `CUA-KiCad/gym_codex/mfm_agent.py`).
    retry_policy = "fixed"
    retry_nudge = ("Your previous attempt at this turn produced no usable ./actions.json. "
                   "Write it now, before anything else.")
    #: What a call that succeeded but parsed to nothing is reported as; None leaves the
    #: backend's own error in place.
    unusable_error: str | None = None
    #: Write AGENTS.md when the first observation arrives (the KiCad arm); False leaves
    #: it to a driver that writes it when it loads the task.
    write_system_prompt_on_first_step = False

    def __init__(
        self,
        *,
        visible: Path,
        record_dir: Path,
        log: EpisodeLog,
        codex: Any,
        analyzer_retries: int,
        sinks: Sequence[MemorySink] = (),
    ) -> None:
        self.visible = Path(visible)
        self.workspace = self.visible
        self.record_dir = Path(record_dir)
        self.log = log
        self.codex = codex
        self.analyzer_retries = analyzer_retries
        self.sinks: list[MemorySink] = list(sinks)
        self.queue: deque[dict[str, Any]] = deque()
        self.turn = 0
        self.act_turns = 0
        self.parse_failures = 0
        self.no_op_turns = 0
        self.plan_flushes = 0
        self._initial_written = False
        self._prev_item: dict[str, Any] | None = None
        self._obs: Observation | None = None
        self._finished = False

    # -- hooks the benchmark implements -----------------------------------------

    def system_prompt(self) -> str:
        raise NotImplementedError

    def turn_prompt(self, obs: Observation) -> str:
        raise NotImplementedError

    def initial_section(self, obs: Observation) -> tuple[str, list[str]]:
        """(title, lines) of the episode's first section."""
        raise NotImplementedError

    def section(self, prev_item: dict[str, Any] | None,
                obs: Observation) -> tuple[str, list[str]] | None:
        """(title, lines) of this step's section, or None to write none.

        `prev_item` is the queue item returned on the previous step, or None when there
        was none (the first step, or a step whose model call produced nothing)."""
        raise NotImplementedError

    def flush_reason(self, obs: Observation) -> str | None:
        """Why the rest of the queued plan should be dropped before this step, or None.
        Called every step, before the section is written, whether or not the queue is
        empty (a benchmark may track state across calls here)."""
        return None

    def parse_plan(self, result: dict[str, Any]) -> Plan | None:
        """The plan in a successful backend result, or None when it is unusable."""
        raise NotImplementedError

    def accept_plan(self, plan: Plan, attempt: int, budget: int) -> str | None:
        """A reason to reject a valid plan and ask again (sent as the nudge), or None."""
        return None

    def adopt_plan(self, plan: Plan, result: dict[str, Any]) -> None:
        """What the log gets from a new plan. Default: the [PLAN] block for the next
        section (and every section, under a persistent-plan log)."""
        self.log.set_plan(plan.think, briefing=plan.briefing)

    def after_pop(self, item: dict[str, Any]) -> None:
        """Bookkeeping once a queue item is about to be returned to the driver."""

    def before_retry(self, result: dict[str, Any], attempt: int, budget: int) -> None:
        """A fixed-policy attempt failed and another follows. The benchmark may wait
        here (an infrastructure refusal is not cured by an immediate retry); the
        default does not, which is the loop the measured runs used."""

    def on_no_plan(self, result: dict[str, Any]) -> None:
        """The retry budget is spent and there is no plan."""
        logger.error("[%s] analyzer produced nothing after %d tries", self.arm,
                     self.analyzer_retries)

    # -- the protocol -----------------------------------------------------------

    def note(self, text: str) -> None:
        self.log.add_note(text)
        for sink in self.sinks:
            sink.note(self, text)

    def full_system_prompt(self) -> str:
        """The benchmark's system prompt plus one paragraph per memory that has
        something to tell the model. With no sinks, exactly `system_prompt()`."""
        text = self.system_prompt()
        for sink in self.sinks:
            note = sink.prompt_note(self)
            if note:
                text = text.rstrip("\n") + "\n\n" + note.strip() + "\n"
        return text

    # -- what the episode store asks the benchmark ----------------------------------

    def episode_state(self, obs: Observation) -> dict[str, Any]:
        """The structured state written to `state/state.json` (and tracked per tick
        for the outcome)."""
        return {"step": obs.step, **{k: v for k, v in obs.state.items()}}

    def episode_action(self, item: dict[str, Any]) -> Any:
        """The queue item's entry as JSON."""
        entry = item["entry"]
        return entry if isinstance(entry, (dict, list, str, int, float)) else str(entry)

    def episode_action_kind(self, item: dict[str, Any]) -> str | None:
        """A short label for `same_action` retrieval (e.g. the action's keys)."""
        return None

    def episode_outcome(self, entry: Any, first: dict[str, Any], last: dict[str, Any],
                        notes: list[str], flushed: bool) -> tuple[dict[str, Any], list[str], str]:
        """(outcome fields, tags, one-line summary) for `outcome.json` and the index."""
        return {}, [], ""

    def episode_index_fields(self, first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
        """Extra columns for `index.jsonl` (MCU: x, z, gui_open)."""
        return {}

    def observe(self, obs: Observation) -> None:
        # The flush decision first: it is where the benchmark updates what it knows
        # about this observation (MCU's verification state), and the sinks' state for
        # the step is computed once, here, so it must see that update.
        reason = self.flush_reason(obs)
        for sink in self.sinks:
            sink.observe(self, obs)
        if reason and self.queue:
            logger.info("[%s] %s: flushing %d queued step(s) and re-planning",
                        self.arm, reason, len(self.queue))
            self.queue.clear()
            self.plan_flushes += 1
        if not self._initial_written:
            title, lines = self.initial_section(obs)
            self.log.write_initial(title, lines)
            if self.write_system_prompt_on_first_step:
                self.codex.write_system_prompt(self.full_system_prompt())
            for sink in self.sinks:
                sink.initial(self, obs)
            self._initial_written = True
        sec = self.section(self._prev_item, obs)
        if sec is not None:
            title, lines = sec
            self.log.write_section(title, lines)
            for sink in self.sinks:
                sink.open(self, obs, title, lines)
        # Consumed. Without this a failed refill would leave the item set and every
        # later step would re-log the same action as if it had been issued again.
        self._prev_item = None
        self._obs = obs

    def act(self, obs: Observation) -> dict[str, Any] | None:
        """The next queue item, refilling first if the queue is empty; None when the
        model produced no plan (the driver falls back to its default action)."""
        if not self.queue and not self.refill(obs):
            self._prev_item = None
            return None
        item = self.queue.popleft()
        self._prev_item = item
        for sink in self.sinks:
            sink.act(self, item)
        self.after_pop(item)
        return item

    def step(self, obs: Observation) -> dict[str, Any] | None:
        self.observe(obs)
        return self.act(obs)

    def refill(self, obs: Observation) -> bool:
        """One model turn: publish the view, prompt, retry, parse, queue. True when a
        plan was queued."""
        for sink in self.sinks:
            sink.refill(self, obs)
        for sink in self.sinks:
            sink.publish(self, self.visible)

        # Unconditional, not on demand. The comparison arms are handed their frames every
        # step; an analyzer that has to decide to look is not information-matched to
        # them (measured: 8 turns, 0 view_image calls when it was optional).
        images = [self.visible / obs.attachment] if obs.attachment else []
        base_prompt = self.turn_prompt(obs)

        extend = self.retry_policy == "extend"
        attempt, budget, refusals, capacity = 0, self.analyzer_retries, 0, 0
        nudge = self.retry_nudge
        result: dict[str, Any] = {"ok": False, "error": "not attempted", "artifact": None,
                                  "actions_json": None, "message": ""}
        while attempt < budget:
            attempt += 1
            prompt = base_prompt if attempt == 1 else f"{base_prompt}\n\n{nudge}"
            result = self.codex.run(prompt, images=images)
            nudge = self.retry_nudge
            plan = self.parse_plan(result) if result.get("ok") else None
            if plan is not None:
                reason = self.accept_plan(plan, attempt, budget)
                if reason is None:
                    self._adopt(plan, result)
                    return True
                nudge = reason
                continue
            if result.get("ok") and self.unusable_error is not None:
                result = dict(result, ok=False, error=self.unusable_error)
            err = result.get("error")
            if extend:
                if errors.is_filter_refusal(err) and refusals < errors.FILTER_RETRIES:
                    refusals += 1
                    budget += 1
                elif errors.is_transient_infra(err) and capacity < errors.CAPACITY_RETRIES:
                    capacity += 1
                    budget += 1
                    time.sleep(min(2 ** capacity, 60))
                elif attempt < budget:
                    time.sleep(min(2 ** attempt, 30))
            elif attempt < budget:
                self.before_retry(result, attempt, budget)
            logger.warning("[%s] turn %d attempt %d/%d produced no usable plan (%s%s)",
                           self.arm, self.codex.calls, attempt, budget,
                           "context overflow; " if result.get("overflow") else "", err)
        if extend and errors.is_transient_infra(result.get("error")):
            # The infrastructure's failure, not the model's: hand it to the driver's
            # own backoff rather than scoring it as a no-op step.
            raise RuntimeError(f"codex unavailable: {result.get('error')}")
        self.on_no_plan(result)
        return False

    def _adopt(self, plan: Plan, result: dict[str, Any]) -> None:
        self.adopt_plan(plan, result)
        for sink in self.sinks:
            sink.plan(self, plan)
        offset = 0
        total = len(plan.steps)
        for entry_index, (entry, ticks) in enumerate(zip(plan.entries, plan.ticks), 1):
            for tick in range(1, ticks + 1):
                offset += 1
                self.queue.append({
                    "entry": entry, "payload": plan.steps[offset - 1], "think": plan.think,
                    "tick": tick, "ticks": ticks, "index": offset, "total": total,
                    "entry_index": entry_index, "entries_total": len(plan.entries),
                })

    def finish(self, reward: Any = None, error: Any = None, **outcome: Any) -> None:
        """The episode ended (the driver's `finish(reward, error)`); closes the open
        episode in every sink. Safe to call more than once."""
        if self._finished:
            return
        self._finished = True
        for sink in self.sinks:
            sink.close(self, reward=reward, error=error, **outcome)

    def audit(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            **self.codex.audit(),
            "turns": self.turn,
            "act_turns": self.act_turns,
            "parse_failures": self.parse_failures,
            "no_op_turns": self.no_op_turns,
            "workspace": str(self.visible),
        }
