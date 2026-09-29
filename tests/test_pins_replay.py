"""A scripted KiCad episode replayed through the PRO-LONG agent with the fake codex.

Pins everything the benchmark sees and everything the driver gets back:
  - `logs.txt` and `AGENTS.md` byte for byte, and the frame files written
  - every prompt handed to codex, its attached images, resume flag and environment
  - every action returned to the driver, in order
No engine, no model. The trace exercises the paths the measured runs take: plan drain,
refill, a failed attempt then a nudged retry, env feedback, an invalid action, and a
terminate.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from conftest import check_pin


def _norm(text: str, tmp: Path) -> str:
    return text.replace(str(tmp), "<tmp>")


def _frame(step: int) -> np.ndarray:
    frame = np.zeros((36, 64, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % 36, :, 1] = 255
    return frame


def _dump_calls(handle, tmp: Path) -> str:
    rows = []
    for c in handle.recorded():
        rows.append({"i": c["i"], "cwd": _norm(c["cwd"], tmp), "resume": c["resume"],
                     "images": [_norm(p, tmp) for p in c["images"]],
                     "env": {k: (_norm(v, tmp) if v else v) for k, v in c["env"].items()},
                     "argv": [_norm(a, tmp) for a in c["argv"]],
                     "prompt": c["prompt"]})
    return json.dumps(rows, indent=1)


def drive_kicad(agent, fake_codex) -> list[dict]:
    fake_codex.reply({"actions": [{"action": "click", "coordinate": [500, 500]},
                                  {"action": "type", "text": "R1"}]},
                     "Placing the resistor.\n[PLAN]\nclick canvas, type")
    fake_codex.reply({"actions": [{"action": "fly", "coordinate": [1, 1]},
                                  {"action": "click", "coordinate": [200, 2000]}]},
                     "[PLAN]\nsecond batch")
    fake_codex.reply(None, "no file this time")                    # attempt 1 fails
    fake_codex.reply({"actions": [{"action": "key", "keys": ["ctrl", "s"]}]},
                     "[PLAN]\nsave")                                  # attempt 2
    fake_codex.reply({"terminate": {"status": "success", "reason": "saved"}}, "done")

    outputs = []
    png = lambda step: bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes([step] * 32)
    for step in range(4):
        if step == 2:
            agent.add_feedback("env error: dialog blocked the click")
        message, calls, done = agent.predict("Add a 10k resistor.", png(step), step, 8)
        outputs.append({"step": step, "message": message, "calls": calls, "done": done})
        if done:
            break

    return outputs


def test_kicad_replay(tmp_path, fake_codex, monkeypatch):
    from gym_codex.prolong_agent import ProlongGuiAgent
    monkeypatch.setattr("time.sleep", lambda s: None)

    ws = tmp_path / "ws"
    agent = ProlongGuiAgent(
        workspace=ws, model="gpt-5.6-sol", effort="low", max_steps=8,
        transcript_dir=None, codex_home=str(tmp_path / "home"), session_turns=None,
        base_url=None)

    outputs = drive_kicad(agent, fake_codex)
    visible = agent.visible
    check_pin("kicad_logs.txt", _norm((visible / "logs.txt").read_text(), tmp_path))
    check_pin("kicad_agents.md", (visible / "AGENTS.md").read_text())
    check_pin("kicad_frames.txt", "\n".join(sorted(p.name for p in (visible / "frames").iterdir())))
    check_pin("kicad_calls.json", _dump_calls(fake_codex, tmp_path))
    check_pin("kicad_outputs.json", json.dumps(outputs, indent=1))
    audit = agent.audit()
    audit.pop("vision_audit_source", None)
    audit["workspace"] = _norm(audit["workspace"], tmp_path)
    check_pin("kicad_audit.json", json.dumps(audit, indent=1, sort_keys=True))
