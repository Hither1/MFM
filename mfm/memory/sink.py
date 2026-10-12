"""A memory written beside the log, from the same call sites.

The agent base calls these at fixed points of the turn protocol (see
`mfm.agent.base.MemoryAgent`). Every method is a no-op here, so a sink implements only
the moments it cares about. The log itself is not a sink: its calls carry rendering
arguments the benchmark owns, so the base calls it directly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from mfm.agent.base import MemoryAgent, Observation, Plan


class MemorySink:
    def prompt_note(self, agent: "MemoryAgent") -> str | None:
        """A paragraph appended to the system prompt telling the model this memory
        exists and how to use it. None for a memory the model is not told about."""
        return None

    def observe(self, agent: "MemoryAgent", obs: "Observation") -> None:
        """Every observation, before anything is written for it."""

    def initial(self, agent: "MemoryAgent", obs: "Observation") -> None:
        """The episode's first observation, before any action."""

    def open(self, agent: "MemoryAgent", obs: "Observation", title: str,
             lines: list[str]) -> None:
        """A log section was written for this observation (and the previous action)."""

    def turn_note(self, agent: "MemoryAgent", obs: "Observation") -> str | None:
        """A line appended to this turn's prompt, or None. The model does not pull from
        a memory it is only told about (0 query-tool calls in 1,410 commands on KiCad
        GPT-6), so a memory that can establish one fact cheaply pushes it here."""
        return None

    def refill(self, agent: "MemoryAgent", obs: "Observation") -> None:
        """The queue is empty and a model turn is about to run. Whatever entry was still
        open did not run to its last tick (the plan was flushed, or the previous turn
        produced nothing and the driver's default action ran instead)."""

    def plan(self, agent: "MemoryAgent", plan: "Plan") -> None:
        """A model call produced a plan; the queue is about to be filled from it."""

    def act(self, agent: "MemoryAgent", item: dict[str, Any]) -> None:
        """One queue item was popped and is being returned to the driver."""

    def note(self, agent: "MemoryAgent", text: str) -> None:
        """A harness-side note was added to the log."""

    def publish(self, agent: "MemoryAgent", visible: "Path") -> None:
        """The visible workspace is being rebuilt for a model call."""

    def close(self, agent: "MemoryAgent", **outcome: Any) -> None:
        """The episode ended."""
