"""The MFM arm on the pinned traces: the log, the prompts and the returned actions must
be exactly the baseline's (the store is written beside them, never in their place), the
system prompt differs by exactly the appended paragraph, and the `episodes/` tree and
index are pinned in their own right.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import check_pin, pin_path
import test_pins_replay as R


def _tree(root: Path) -> str:
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.endswith(".tmp"):
            rel = p.relative_to(root).as_posix()
            if p.suffix in (".json", ".jsonl", ".txt"):
                lines.append(f"### {rel}\n{p.read_text(encoding='utf-8').replace(str(root.parent), '<tmp>')}")
            else:
                lines.append(f"### {rel}  ({p.stat().st_size} bytes)")
    return "\n".join(lines) + "\n"


def test_mcu_store(tmp_path, fake_codex):
    from mc_agent.action_space import MinerRLActionSpace
    from mc_agent.prolong_agent import ProlongAgent
    from prolong_mc.mfm_prompts import MFM_MEMORY_NOTE

    ws = tmp_path / "ws"
    agent = ProlongAgent(
        action_space=MinerRLActionSpace(), provider=None, model="gpt-5.6-sol",
        workspace=ws, transcript_dir=None, reasoning_effort="low", base_url=None,
        codex_home=tmp_path / "home", action_cap=15, repeat_cap=20, step_cap=40,
        analyzer_retries=5, milestone_hint=True, episodes=True)
    outputs = R.drive_mcu(agent, fake_codex)
    agent.save_state(tmp_path)

    assert R._norm((ws / "logs.txt").read_text(), tmp_path) == pin_path("mcu_logs.txt").read_text()
    baseline_agents = pin_path("mcu_agents.md").read_text()
    assert (ws / "AGENTS.md").read_text() == baseline_agents.rstrip("\n") + "\n\n" + MFM_MEMORY_NOTE.strip() + "\n"
    assert json.dumps(outputs, indent=1) == pin_path("mcu_outputs.json").read_text()
    calls = json.loads(R._dump_calls(fake_codex, tmp_path))
    pinned = json.loads(pin_path("mcu_calls.json").read_text())
    assert [c["prompt"] for c in calls] == [c["prompt"] for c in pinned]
    assert [c["argv"] for c in calls] == [c["argv"] for c in pinned]
    audit = json.loads((tmp_path / "prolong_vision_audit.json").read_text())
    audit.pop("vision_audit_source", None)
    assert set(audit) - set(json.loads(pin_path("mcu_audit_keys.json").read_text())) == {"mfm"}
    assert audit["mfm"]["n"] == len([l for l in (ws / "index.jsonl").read_text().splitlines() if l])
    assert (ws / "tools" / "episodes.py").exists()
    check_pin("mcu_episodes.txt", _tree(ws / "episodes") + "### index.jsonl\n" + (ws / "index.jsonl").read_text())


def test_kicad_store(tmp_path, fake_codex, monkeypatch):
    from gym_codex import memory_agents
    from gym_codex.mfm_prompts import MFM_MEMORY_NOTE
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)

    ws = tmp_path / "ws"
    agent = memory_agents.make_agent(
        "prolong", workspace=ws, model="gpt-5.6-sol", effort="low", max_steps=8,
        transcript_dir=None, codex_home=str(tmp_path / "home"), session_turns=None,
        base_url=None, episodes=True)          # the store alone: the plan queue is section 4
    outputs = R.drive_kicad(agent, fake_codex)
    agent.finish(1.0, None)

    assert R._norm((ws / "logs.txt").read_text(), tmp_path) == pin_path("kicad_logs.txt").read_text()
    baseline_agents = pin_path("kicad_agents.md").read_text()
    assert (ws / "AGENTS.md").read_text() == baseline_agents.rstrip("\n") + "\n\n" + MFM_MEMORY_NOTE.strip() + "\n"
    assert json.dumps(outputs, indent=1) == pin_path("kicad_outputs.json").read_text()
    calls = json.loads(R._dump_calls(fake_codex, tmp_path))
    pinned = json.loads(pin_path("kicad_calls.json").read_text())
    assert [c["prompt"] for c in calls] == [c["prompt"] for c in pinned]
    audit = agent.audit()
    assert audit["mfm"]["n"] == 5      # initial + 4 turns
    check_pin("kicad_episodes.txt", _tree(ws / "episodes") + "### index.jsonl\n" + (ws / "index.jsonl").read_text())


def test_kicad_plan_queue(tmp_path, fake_codex, monkeypatch):
    """The MFM arm's queue: three batches from one call, a flush on an unchanged screen
    after an input batch, and a queued terminate re-decided on the current screen."""
    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    agent = memory_agents.make_agent(
        "mfm", workspace=tmp_path / "ws", model="gpt-5.6-sol", effort="low", max_steps=10,
        transcript_dir=None, codex_home=str(tmp_path / "home"), session_turns=None, base_url=None)
    click = {"actions": [{"action": "click", "coordinate": [100, 100]}]}
    fake_codex.reply({"plan": [click, {"actions": [{"action": "key", "keys": ["a"]}]},
                               {"terminate": {"status": "success"}}]}, "[PLAN]\nthree")
    fake_codex.reply({"terminate": {"status": "success", "reason": "confirmed"}}, "[PLAN]\nend")
    png = lambda k: b"\x89PNG" + bytes([k] * 16)
    # step 1: call 1, batch 1 (click). step 2: screen changed -> batch 2 drained (key).
    # step 3: screen unchanged after the key batch -> flush; queue head was terminate ->
    # call 2 decides on the current screen.
    r1 = agent.predict("t", png(1), 0, 10)
    r2 = agent.predict("t", png(2), 1, 10)
    r3 = agent.predict("t", png(2), 2, 10)
    calls = fake_codex.recorded()
    assert len(calls) == 2, [c["i"] for c in calls]
    assert r1[1][0]["function"]["name"] == "computer" and not r1[2]
    assert r2[1][0]["function"]["arguments"]["actions"][0]["action"] == "key" and not r2[2]
    assert r3[2] and r3[1][0]["function"]["arguments"]["reason"] == "confirmed"
    assert agent.plan_flushes == 1
    log = (tmp_path / "ws" / "logs.txt").read_text()
    assert "Turn 2 | Step 2/10 | Plan Step 2/3" in log
    assert agent.audit()["mfm"]["plan_queue"] is True


def test_kicad_workspace_has_the_promised_zoom_tool(tmp_path, fake_codex, monkeypatch):
    """Both KiCad arms' prompts tell the model about `./tools/zoom.py`; the file must
    exist and work. It never did: every zoom attempt in the measured runs failed with
    "No such file or directory", and the model then gave up looking at earlier
    screens (2 frame re-opens in 1,410 shell commands on GPT-6)."""
    import os
    import subprocess
    import sys

    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    for arm in ("prolong", "mfm"):
        ws = tmp_path / arm
        memory_agents.make_agent(
            arm, workspace=ws, model="gpt-5.6-sol", effort="low", max_steps=8,
            transcript_dir=None, codex_home=str(tmp_path / "home"), session_turns=None,
            base_url=None)
        tool = ws / "tools" / "zoom.py"
        assert tool.exists() and os.access(tool, os.X_OK), arm
        from PIL import Image
        frame = ws / "frame.png"
        Image.new("RGB", (1920, 1080), (10, 20, 30)).save(frame)
        out = ws / "zoom.png"
        r = subprocess.run([sys.executable, str(tool), str(frame), "100", "200", "50", "25",
                            str(out)], capture_output=True, text=True, cwd=ws)
        assert r.returncode == 0, r.stderr
        assert Image.open(out).size == (200, 100), arm
