"""Pin 5: the MCU ablation arms (`--log-window N`, `--stateless`), with and without the
episode store.

Two layers of pin. The baseline layer (no store) freezes what the ablated arms write
and show: the record log, the visible workspace after the last publish, every prompt
and attached image, every action. The store layer freezes what `episodes/` looks like
in the visible workspace under each ablation and what the system prompt says about it;
it is the part the ablation-leak fixes were allowed to move.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import check_pin
from test_pins_replay import _dump_calls, _norm, drive_mcu


def _listing(root: Path, tmp: Path) -> str:
    return "\n".join(sorted(_norm(p.as_posix(), tmp) for p in root.rglob("*") if p.is_file()))


def _agent(tmp_path: Path, **kw):
    from mc_agent.action_space import MinerRLActionSpace
    from mc_agent.prolong_agent import ProlongAgent
    return ProlongAgent(
        action_space=MinerRLActionSpace(), provider=None, model="gpt-5.6-sol",
        workspace=tmp_path / "ws", transcript_dir=None, reasoning_effort="low",
        base_url=None, codex_home=tmp_path / "home", action_cap=15, repeat_cap=20,
        step_cap=40, analyzer_retries=5, milestone_hint=True, **kw)


def _run(tmp_path: Path, fake_codex, tag: str, **kw) -> None:
    agent = _agent(tmp_path, **kw)
    outputs = drive_mcu(agent, fake_codex)
    agent.save_state(tmp_path)
    ws, record = agent.visible, agent.record_dir
    check_pin(f"abl_{tag}_logs.txt", _norm((record / "logs.txt").read_text(), tmp_path))
    check_pin(f"abl_{tag}_visible.txt", _listing(ws, tmp_path))
    check_pin(f"abl_{tag}_calls.json", _dump_calls(fake_codex, tmp_path))
    check_pin(f"abl_{tag}_outputs.json", json.dumps(outputs, indent=1))
    audit = json.loads((tmp_path / "prolong_vision_audit.json").read_text())
    check_pin(f"abl_{tag}_audit_ablation.json", json.dumps(
        {k: audit.get(k) for k in ("log_window", "stateless", "ablation_enforced",
                                   "frames_visible", "files_removed")}, indent=1))
    if kw.get("episodes"):
        check_pin(f"abl_{tag}_agents.md", (ws / "AGENTS.md").read_text())
        check_pin(f"abl_{tag}_record_episodes.txt",
                  "\n".join(sorted(_norm(p.as_posix(), tmp_path)
                                   for p in (record / "episodes").rglob("*") if p.is_file())))


def test_window_baseline(tmp_path, fake_codex):
    _run(tmp_path, fake_codex, "window3", log_window=3)


def test_stateless_baseline(tmp_path, fake_codex):
    _run(tmp_path, fake_codex, "stateless", stateless=True)


def test_window_store(tmp_path, fake_codex):
    _run(tmp_path, fake_codex, "window3_mfm", log_window=3, episodes=True)


def test_stateless_store(tmp_path, fake_codex):
    _run(tmp_path, fake_codex, "stateless_mfm", stateless=True, episodes=True)
