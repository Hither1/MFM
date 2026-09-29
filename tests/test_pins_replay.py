"""Pin 3: a scripted episode replayed through each PRO-LONG agent with the fake codex.

Pins everything the benchmark sees and everything the driver gets back:
  - `logs.txt` and `AGENTS.md` byte for byte, and the frame files written
  - every prompt handed to codex, its attached images, resume flag and environment
  - every action returned to the driver, in order
No engine, no model. The trace exercises the paths the measured runs take: plan drain,
refill, a failed attempt then a nudged retry, a verification flush (MCU), env feedback
and an invalid action (KiCad), and a terminate.
"""
from __future__ import annotations

import json
import os
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


def _mcu_info(step: int, verified: bool = False) -> dict:
    x = 1.0 + 0.3 * step
    inv = {"0": {"type": "spruce_log", "quantity": 3 + step // 4},
           "1": {"type": "wooden_pickaxe", "quantity": 1},
           "9": {"type": "cobblestone", "quantity": 2 * step}}
    spec = [{"identity": "mine_log", "event": "mine", "objects": ["log"], "done": 1},
            {"identity": "crafting_table", "event": "craft", "objects": ["crafting_table"],
             "done": int(verified)}]
    return {"player_pos": {"x": x, "y": 64.0, "z": 2.0 - 0.1 * step, "pitch": 10.0, "yaw": 90.0},
            "inventory": inv, "isGuiOpen": step % 5 == 4,
            "equipped_items": {"mainhand": {"type": "wooden_pickaxe"}},
            "health": 20, "food_level": 18,
            "location_stats": {"light_level": 7, "can_see_sky": "true"},
            "mobs": [{"name": "zombie"}] if step % 3 == 0 else [],
            "milestone_spec": spec}


def _dump_calls(handle, tmp: Path) -> str:
    rows = []
    for c in handle.recorded():
        rows.append({"i": c["i"], "cwd": _norm(c["cwd"], tmp), "resume": c["resume"],
                     "images": [_norm(p, tmp) for p in c["images"]],
                     "env": {k: (_norm(v, tmp) if v else v) for k, v in c["env"].items()},
                     "argv": [_norm(a, tmp) for a in c["argv"]],
                     "prompt": c["prompt"]})
    return json.dumps(rows, indent=1)


def drive_mcu(agent, fake_codex) -> list[dict]:
    agent.load_system_prompt("Mine a diamond from scratch.", "Platform note: MineRL keys.")
    # call 1: a two-entry plan (4 ticks)
    fake_codex.reply({"actions": [{"action": {"forward": 1, "sprint": 1}, "repeat": 3},
                                  {"action": {"camera": [0, 30]}, "repeat": 1}]},
                     "Heading north to the trees.\n[PLAN]\nwalk 3, turn right")
    # call 2: no artifact (the nudged retry path), call 3: a plan of 6 ticks
    fake_codex.reply(None, "thinking out loud, forgot the file")
    fake_codex.reply({"actions": [{"action": {"attack": 1}, "repeat": 4},
                                  {"action": {"hotbar.2": 1}, "repeat": 1},
                                  {"action": {"ESC": 1}, "repeat": 1}]},
                     "Chopping.\n[PLAN]\nattack 4, select pickaxe, esc")
    # call 4: after the verification flush
    fake_codex.reply({"actions": [{"action": {"inventory": 1}, "repeat": 2}]},
                     "[PLAN]\nopen inventory")

    outputs = []
    hints = {0: "Milestones: 1/2 done. Next: crafting_table.",
             7: "The environment HAS verified the task as complete."}
    hint = ""
    for step in range(12):
        hint = hints.get(step, hint)
        verified = step >= 7
        if step == 6:
            agent.on_esc_rejected(step)
        think, wire, mem = agent.get_action([_frame(step)], [], [], current_step=step,
                                            milestone_hint=hint, info=_mcu_info(step, verified))
        outputs.append({"step": step, "think": think, "wire": wire, "mem": mem})
    return outputs


def test_mcu_replay(tmp_path, fake_codex):
    from mc_agent.action_space import MinerRLActionSpace
    from mc_agent.prolong_agent import ProlongAgent

    ws = tmp_path / "ws"
    agent = ProlongAgent(
        action_space=MinerRLActionSpace(), provider=None, model="gpt-5.6-sol",
        workspace=ws, transcript_dir=None, reasoning_effort="low", base_url=None,
        codex_home=tmp_path / "home", action_cap=15, repeat_cap=20, step_cap=40,
        analyzer_retries=5, milestone_hint=True)
    outputs = drive_mcu(agent, fake_codex)
    agent.save_state(tmp_path)

    check_pin("mcu_logs.txt", _norm((ws / "logs.txt").read_text(), tmp_path))
    check_pin("mcu_agents.md", (ws / "AGENTS.md").read_text())
    check_pin("mcu_frames.txt", "\n".join(sorted(p.name for p in (ws / "frames").iterdir())))
    check_pin("mcu_calls.json", _dump_calls(fake_codex, tmp_path))
    check_pin("mcu_outputs.json", json.dumps(outputs, indent=1))
    audit = json.loads((tmp_path / "prolong_vision_audit.json").read_text())
    audit.pop("vision_audit_source", None)
    check_pin("mcu_audit_keys.json", json.dumps(sorted(audit), indent=1))
    check_pin("mcu_workspace_files.txt", (tmp_path / "prolong_workspace_files.txt").read_text())


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
