"""The KiCad system prompts (AGENTS.md) and turn prompts, verbatim.

The MFM arm may append one paragraph to the system prompt; the baseline arms must
render exactly these bytes.
"""
from __future__ import annotations

from conftest import check_pin

TASK = "Mine a diamond from scratch."
PLATFORM = "Platform note: keys are MineRL wire keys."


def test_kicad_prompts():
    from gym_codex import prompts_prolong
    out = [f"##### system max_steps=20\n", prompts_prolong.build_system_prompt(20), "\n"]
    for first, turns, step in ((True, 0, 1), (False, 1, 2), (False, 8, 9), (False, 16, 17)):
        out.append(f"##### turn first={first} turns={turns} step={step}\n")
        out.append(prompts_prolong.build_turn_prompt(first, turns, step, 20))
        out.append("\n")
    check_pin("prompts_kicad.txt", "".join(out))
