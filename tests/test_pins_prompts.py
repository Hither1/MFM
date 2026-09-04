"""Pin 2: the system prompts (AGENTS.md) and turn prompts, verbatim, per benchmark.

The MFM arm may append one paragraph to the system prompt; the baseline arms must
render exactly these bytes.
"""
from __future__ import annotations

from conftest import check_pin

TASK = "Mine a diamond from scratch."
PLATFORM = "Platform note: keys are MineRL wire keys."


def test_mcu_prompts():
    from prolong_mc import prompts
    out = []
    for window, stateless, hint in ((None, False, True), (None, False, False),
                                    (5, False, True), (None, True, True)):  # window=-1 system prompt: pre-existing TypeError in prompts.py:340, not pinned
        out.append(f"##### system window={window} stateless={stateless} milestone_hint={hint}\n")
        out.append(prompts.build_system_prompt(
            task_text=TASK, action_cap=15, step_cap=40, repeat_cap=20, log_window=window,
            stateless=stateless, milestone_hint=hint, platform_prompt=PLATFORM))
        out.append("\n")
    for window, first, attached in ((None, True, True), (None, False, True),
                                    (5, False, True), (0, False, False), (-1, True, True), (-1, False, True)):
        out.append(f"##### turn window={window} first={first} attached={attached}\n")
        out.append(prompts.build_turn_prompt("logs.txt", first, window, attached,
                                             state_text="[STATE] pos=(1.00, 64.00, 2.00)"))
        out.append("\n")
    check_pin("prompts_mcu.txt", "".join(out))


def test_kicad_prompts():
    from gym_codex import prompts_prolong
    out = [f"##### system max_steps=20\n", prompts_prolong.build_system_prompt(20), "\n"]
    for first, turns, step in ((True, 0, 1), (False, 1, 2), (False, 8, 9), (False, 16, 17)):
        out.append(f"##### turn first={first} turns={turns} step={step}\n")
        out.append(prompts_prolong.build_turn_prompt(first, turns, step, 20))
        out.append("\n")
    check_pin("prompts_kicad.txt", "".join(out))
