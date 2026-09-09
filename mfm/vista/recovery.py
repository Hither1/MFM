"""The prompts a fresh or resumed thread starts from (upstream `recovery.py`).

A handoff, not a summary: the environment's record (the present observation, the last
action's result, the recent history) as JSON, then the agent's own notes (GUIDE.md and
the checkpointed working memory), then the objective. The objective sentence is the
benchmark's ("Complete the game with as few game actions as possible." upstream).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CompactRecovery:
    guide: str
    working_memory: str
    current_observation: dict[str, Any]
    last_action_result: dict[str, Any] | None
    objective_history: dict[str, Any]
    image_paths: tuple[Path, ...]
    reason: str = ""


@dataclass(frozen=True)
class RuntimeRecovery:
    boundary_turn: int
    guide: str | None
    working_memory: str | None
    current_observation: dict[str, Any]
    last_action_result: dict[str, Any] | None
    objective_history: dict[str, Any]
    image_paths: tuple[Path, ...]


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def initial_prompt(metadata: dict[str, Any], objective: str) -> str:
    return "\n".join(["Current observation:", _dumps(metadata), "", objective])


def compact_recovery_prompt(recovery: CompactRecovery, objective: str) -> str:
    return _recovery_prompt(current_observation=recovery.current_observation,
                            last_action_result=recovery.last_action_result,
                            objective_history=recovery.objective_history,
                            guide=recovery.guide, working_memory=recovery.working_memory,
                            objective=objective)


def runtime_recovery_prompt(recovery: RuntimeRecovery, objective: str) -> str:
    return "\n".join([
        "The player runtime restarted without changing the environment state.",
        "Environment record:",
        _dumps({"current_observation": recovery.current_observation,
                "last_action_result": recovery.last_action_result}),
        "", objective])


def fresh_runtime_recovery_prompt(recovery: RuntimeRecovery, objective: str) -> str:
    return "\n".join([
        "A fresh player is continuing from the unchanged environment state.",
        _recovery_prompt(current_observation=recovery.current_observation,
                         last_action_result=recovery.last_action_result,
                         objective_history=recovery.objective_history,
                         guide=recovery.guide, working_memory=recovery.working_memory,
                         objective=objective)])


def continuation_prompt(current_observation: dict[str, Any], objective: str) -> str:
    return "\n".join(["Current environment record:", _dumps(current_observation), "", objective])


NONTERMINAL_CONTINUATION_PROMPT = (
    "The environment is still active. Context limits are handled automatically. Continue."
)

CHECKPOINT_PROMPT = (
    '<codex_internal_context source="compact_checkpoint">\n'
    "Call save_compact_checkpoint now as your first and only action, then end this turn.\n"
    "</codex_internal_context>"
)


def _recovery_prompt(*, current_observation: dict[str, Any],
                     last_action_result: dict[str, Any] | None,
                     objective_history: dict[str, Any], guide: Any, working_memory: Any,
                     objective: str) -> str:
    return "\n".join([
        "Environment record:",
        _dumps({"current_observation": current_observation,
                "last_action_result": last_action_result,
                "recent_history": objective_history}),
        "",
        "Agent-authored notes:",
        _dumps({"guide": guide, "working_memory": working_memory}),
        "", objective])
