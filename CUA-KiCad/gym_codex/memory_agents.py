"""The memory arms on a cua-lite GUI episode.

Every arm presents the interface ``run_eval.py`` drives -- ``predict(instruction,
screenshot_png, step_idx, max_steps) -> (reply, tool_calls, done)``, ``add_feedback``,
``audit`` -- and emits exactly the direct arm's tool calls through
``gym_codex.actions.parse_batch``. What differs is what the model remembers between
steps:

- ``CodexGuiAgent`` (direct, ``codex_gui_agent.py``): nothing but a text list of prior
  actions, resent each call.
- ``ProlongGuiAgent`` with ``log_only`` (PRO-LONG, ``prolong_agent.py``): an append-only
  ``logs.txt`` (one section per turn: feedback, screenshot path, executed actions, the
  model's own plan) and a codex thread resumed across turns under an age cap.
- ``VistaGuiAgent`` (VISTA, ``vista_agent.py``): one app-server thread, the screenshot
  archive behind ``inspect``, two notes files.
- ``ProlongGuiAgent`` with the episode store (MFM): the log plus one episode per action
  batch (screenshot, state, action, outcome), the index and its query tool, a
  multi-batch plan queue; ``mfm-carry`` adds the finished tasks' records.

An episode is one task: the workspace lives under the task's output directory and is
created empty for it.
"""
from __future__ import annotations

from typing import Any

from gym_codex.prolong_agent import ProlongGuiAgent

#: The MFM arms as the paper's runs configured them: one design call at high effort
#: before the first action turn (`mfm_prompts.DESIGN_PROMPT`), the conventions
#: paragraph (`mfm_prompts.CONVENTIONS_NOTE`) and, where memory is carried across
#: tasks, each finished task's score beside its record (`previous/outcomes.md`).
MFM: dict[str, Any] = dict(design=True, design_effort="high", conventions=True)

#: What `run_eval.py` builds each memory arm with, beside the run's own arguments.
ARMS: dict[str, dict[str, Any]] = {
    "prolong-logonly": {},
    "vista": {},
    "mfm": MFM,
    "mfm-carry": dict(MFM, carry_outcomes=True),
}


def make_agent(kind: str, **kw: Any):
    if kind == "prolong-logonly":
        # PRO-LONG with the log as its only persistent memory: the model's own files
        # are taken back every turn (EpisodeLog log_only).
        return ProlongGuiAgent(log_only=True, **kw)
    if kind in ("mfm", "mfm-carry"):
        # The log plus the episode store and the plan queue; `mfm-carry` is given
        # `carry_dir` by the driver and links the finished tasks' records.
        return ProlongGuiAgent(episodes=True, plan_queue=True, recall=True, **kw)
    if kind == "vista":
        from gym_codex.vista_agent import VistaGuiAgent
        return VistaGuiAgent(**kw)
    raise ValueError(f"unknown memory arm {kind!r}")
