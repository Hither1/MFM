"""Milestone knowledge from the benchmark's own public config, loaded agent-side.

The green agent used to send `milestones` (live per-milestone completion bits from the
callback that scores the run) and `milestone_spec` (the scoring rules themselves) with
every observation. Both were removed from the wire: the bits are privileged runtime
feedback no participant would have, and the rules are the scoring config. What remains
legitimate is what any participant can do with a public benchmark -- read the task
configs in the repo and encode them into their agent. This module is that reading, done
once, shared by every purple arm so no arm knows more than another.

Verification moves with it: `MilestoneLedger.update` already recomputes completion from
deltas on the cumulative statistics (`mine_block`, `craft_item`, ...) whenever the wire
bits are absent -- the same statistics a human reads on the pause-menu Statistics screen,
against the same rules the scorer applies. The green agent's own scoring is untouched;
what changed is that the agent now derives its progress instead of being told it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent
_TASKS_DIR = _ROOT / "MCU_benchmark" / "task_configs" / "tasks"


def load_milestone_cfg(task: str) -> list[dict[str, Any]]:
    """The `milestone_reward_cfg` for one task category, from the same files
    `src/util.get_tasks` reads -- so the agent-side rules and the scorer's rules cannot
    diverge by coming from different copies. Empty for tasks that define no milestones."""
    task_dir = _TASKS_DIR / task
    if not task_dir.is_dir():
        return []
    cfg: list[dict[str, Any]] = []
    for path in sorted(task_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg.extend(data.get("milestone_reward_cfg") or [])
    return cfg


def synthesize_milestone_info(cfg: list[dict[str, Any]],
                              achieved: dict[str, int],
                              revealed: set[str] | None = None) -> dict[str, Any]:
    """The `milestones` + `milestone_spec` payload in the exact wire shapes the adapters
    and `prolong_mc.log` already consume -- now derived from the agent-side ledger
    instead of received. Full object lists, not the wire's old `[:4]` truncation.

    `revealed` is the ledger's disclosure set under a sequentially-revealed task. It must
    be passed wherever the ledger has one: this payload is how the PRO-LONG arms learn
    their goals, so leaving it out would show that arm the whole A-B-A sequence at step 0
    while the log-based arms saw one goal at a time -- two arms, two different tasks.
    None (the default) discloses everything, which is every pre-existing task.
    """
    rules = [c for c in cfg if revealed is None or c.get("identity") in revealed]
    bits = {c["identity"]: int(c["identity"] in achieved) for c in rules}
    spec = [
        {
            "identity": c.get("identity"),
            "event": c.get("event"),
            "objects": list(c.get("objects") or []),
            "done": bits.get(c.get("identity"), 0),
        }
        for c in rules
    ]
    return {"milestones": bits, "milestone_spec": spec}


def load_reveal_mode(task: str) -> str:
    """`milestone_reveal` for one task category: "all" (the default, and every task that
    does not set it) or "sequential". Agent-side like the rest of this module -- it
    changes what the agent is told, never what the green agent scores."""
    task_dir = _TASKS_DIR / task
    if not task_dir.is_dir():
        return "all"
    for path in sorted(task_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mode = data.get("milestone_reveal")
        if mode in ("all", "sequential"):
            return mode
    return "all"


def load_given_milestones(task: str) -> list[str]:
    """Milestones whose ITEMS a task config hands the kit at reset (`given_milestones`, an
    agent-side key the scorer ignores). They are NOT credited -- the ledger keeps them open
    and the checklist says they are cheap. Empty for the from-scratch tasks; the second-half
    start `ender_dragon_half` lists the ten through the diamond ore."""
    task_dir = _TASKS_DIR / task
    if not task_dir.is_dir():
        return []
    given: list[str] = []
    for path in sorted(task_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        given.extend(str(g) for g in (data.get("given_milestones") or []))
    return given

