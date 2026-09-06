"""The log-only ablation of PRO-LONG on KiCad (`prolong-logonly`): the log and the
frames persist, the model's own files do not, and the log itself is the baseline's."""
from __future__ import annotations

import json
from pathlib import Path

import test_pins_replay as R
from conftest import pin_path


def _agent(tmp_path: Path, monkeypatch, kind: str = "prolong-logonly"):
    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    return memory_agents.make_agent(
        kind, workspace=tmp_path / "ws", model="gpt-5.6-sol", effort="low", max_steps=8,
        transcript_dir=None, codex_home=str(tmp_path / "home"), session_turns=None,
        base_url=None)


def test_log_only_takes_the_models_files_back_each_turn(tmp_path, fake_codex, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    # The baseline replay script, with the model also keeping a plan file on turns 1
    # and 2 (the second call reads it back the way the measured runs did).
    fake_codex.reply({"actions": [{"action": "click", "coordinate": [500, 500]},
                                  {"action": "type", "text": "R1"}]},
                     "Placing the resistor.\n[PLAN]\nclick canvas, type",
                     files={"plan.txt": "1. place R1\n"})
    fake_codex.reply({"actions": [{"action": "fly", "coordinate": [1, 1]},
                                  {"action": "click", "coordinate": [200, 2000]}]},
                     "[PLAN]\nsecond batch", files={"plan.txt": "1. place R1 (done)\n2. wire\n"})
    fake_codex.reply(None, "no file this time")
    fake_codex.reply({"actions": [{"action": "key", "keys": ["ctrl", "s"]}]}, "[PLAN]\nsave")
    fake_codex.reply({"terminate": {"status": "success", "reason": "saved"}}, "done")
    png = lambda step: bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes([step] * 32)
    visible, record = agent.visible, agent.record_dir
    assert visible != record and record.name == "ws_record"
    for step in range(4):
        if step == 2:
            agent.add_feedback("env error: dialog blocked the click")
        message, calls, done = agent.predict("Add a 10k resistor.", png(step), step, 8)
        # The file is taken back at the publish that precedes the call (stashed in the
        # record with the previous turn's content), so the model finds only what it
        # writes in the current turn.
        if step == 0:
            assert (visible / "plan.txt").read_text() == "1. place R1\n"
        if step == 1:
            assert (record / "scratch" / "0002" / "plan.txt").read_text() == "1. place R1\n"
            assert (visible / "plan.txt").read_text() == "1. place R1 (done)\n2. wire\n"
        if step >= 2:
            assert not (visible / "plan.txt").exists()
        if done:
            break
    agent.finish(1.0, None)
    stashed = sorted(p.relative_to(record).as_posix() for p in (record / "scratch").rglob("plan.txt"))
    assert stashed == ["scratch/0002/plan.txt", "scratch/0003/plan.txt"], stashed
    assert (record / "scratch" / "0003" / "plan.txt").read_text() == "1. place R1 (done)\n2. wire\n"
    # The log and the frames are the baseline's, in the record and in the view.
    assert R._norm((record / "logs.txt").read_text(), tmp_path) == pin_path("kicad_logs.txt").read_text()
    # The view is refreshed before each call, so after the last turn it is the record
    # up to that call: a prefix, never a window.
    assert (record / "logs.txt").read_text().startswith((visible / "logs.txt").read_text())
    assert (visible / "logs.txt").read_text().count("\nTurn ") == 5   # Turn 0 + four turns, the last one open
    assert sorted(p.name for p in (visible / "frames").iterdir()) == \
        sorted(p.name for p in (record / "frames").iterdir())
    assert (visible / "tools" / "zoom.py").exists()
    # The prompt promises no persistence beyond the log, and nothing else changed.
    agents = (visible / "AGENTS.md").read_text()
    baseline = pin_path("kicad_agents.md").read_text()
    assert "only the log persists across calls" in agents
    assert "`./` persists across calls" not in agents
    assert len(agents.splitlines()) == len(baseline.splitlines()) + 1
    prompts = [c["prompt"] for c in fake_codex.recorded()]
    assert "state\nthem in your [PLAN]" in prompts[0] and "write\nthem to a file" not in prompts[0]
    assert "write\nthem to a file" not in "".join(prompts[1:])
    audit = agent.audit()
    assert audit["log_only"] is True and audit["files_removed"] >= 2
    assert agent.log.log_only and not agent.log.stateless and agent.log_window is None


def test_baseline_prolong_still_keeps_its_files(tmp_path, fake_codex, monkeypatch):
    agent = _agent(tmp_path, monkeypatch, kind="prolong")
    fake_codex.reply({"actions": [{"action": "click", "coordinate": [1, 1]}]},
                     "[PLAN]\none", files={"plan.txt": "keep me\n"})
    fake_codex.reply({"terminate": {"status": "success", "reason": "x"}}, "done")
    png = lambda step: bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes([step] * 32)
    agent.predict("t", png(0), 0, 8)
    agent.predict("t", png(1), 1, 8)
    assert agent.visible == agent.record_dir
    assert (agent.visible / "plan.txt").read_text() == "keep me\n"
    assert "log_only" not in agent.audit()
