"""Pin 4: the world-model chassis in its logbook mode, replayed with the selftest's fakes.

The logbook arm is the control the MFM arm is built on (same chassis, one append-only
log). This pins what that arm writes and returns so the MFM changes to the chassis
cannot move it: `logs.txt` and `AGENTS.md` byte for byte, every turn prompt, every
action returned to the driver, the workspace listing, and the report keys. The other
modes' system prompts are pinned as well, since they share the prompt assembly.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from conftest import check_pin


def _norm(text: str, tmp: Path) -> str:
    return text.replace(str(tmp), "<tmp>")


def _pov(step: int) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % 360, :, 1] = 255
    return frame


def drive_chassis(root: Path, memory_mode: str, steps: int = 120):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import FakeCodex, fake_info

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1},
           # Never reached, so the loop keeps planning instead of coasting on no-ops.
           {"event": "craft_item", "identity": "iron_pickaxe",
            "objects": ["iron_pickaxe"], "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "ws", task_text="get a log, a table, an iron pickaxe",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=10,
                            step_cap=50, memory_mode=memory_mode,
                            platform_prompt="HOST REFERENCE")
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5},
                                 {"action": {"attack": 1}, "repeat": 3}]},
         "message": "briefing one\n[PLAN]\nwalk then chop",
         "files": {"crafting_notes.md": {"table": "slot 4"}}},
        {"message": "no actions this time"},                      # a failed attempt
        {"actions": {"actions": [{"procedure": "dig_down", "args": {"n": 4}}]},
         "message": "briefing two\n[PLAN]\ndig"},
        {"actions": {"actions": [{"action": {"forward": 1, "jump": 1}, "repeat": 12}]},
         "message": "[PLAN]\nrun"},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
          "message": f"[PLAN]\nchop {i}"} for i in range(20)]
    agent.codex = FakeCodex(agent.memory.root, script)

    info = fake_info(inventory={"oak_log": 1})
    info["pov"] = _pov(0)
    agent.start(info)
    actions = []
    for step in range(1, steps + 1):
        actions.append(agent.next_action(info))
        if step == 8:
            info = fake_info(inventory={"oak_log": 2}, mine_block={"oak_log": 1})
        elif step == 30:
            info = fake_info(inventory={"oak_log": 2, "crafting_table": 1},
                             mine_block={"oak_log": 1}, craft_item={"crafting_table": 1})
        else:
            info = fake_info(inventory={"oak_log": 2 if step > 8 else 1},
                             mine_block={"oak_log": 1} if step > 8 else {})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["location_stats"]["ypos"] = np.array(64.0 - (step // 20))
        info["health"] = np.array(20.0 - (step // 25))
        info["pov"] = _pov(step)
        agent.observe(info, step)
    return agent, actions


def test_chassis_logbook_pins(tmp_path: Path):
    agent, actions = drive_chassis(tmp_path, "logbook")
    ws = agent.memory.root
    check_pin("chassis_logbook_logs.txt", _norm((ws / "logs.txt").read_text(), tmp_path))
    check_pin("chassis_logbook_agents.md", _norm((ws / "AGENTS.md").read_text(), tmp_path))
    check_pin("chassis_logbook_prompts.txt",
              "\n=====\n".join(_norm(p, tmp_path) for p in agent.codex.prompts))
    check_pin("chassis_logbook_actions.json",
              json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v)
                           for k, v in a.items()} for a in actions], sort_keys=True))
    check_pin("chassis_logbook_workspace.txt",
              "\n".join(sorted(p.relative_to(ws.parent).as_posix()
                               for p in ws.parent.rglob("*") if p.is_file())))
    rep = agent.report()
    check_pin("chassis_logbook_report_keys.json",
              json.dumps({"keys": sorted(rep), "memory_mode": rep["memory_mode"],
                          "steps": rep["steps"], "turns": rep["turns"],
                          "milestones": rep["milestones"]}, sort_keys=True, default=str))


def test_chassis_system_prompts_pin():
    from mcu_worldmodel import prompts
    kw = dict(task_text="get a log", progress_block="0/2", graph_summary="",
              plan_summary="", discipline_summary="", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE")
    out = {mode: hashlib.sha256(prompts.act_prompt(**kw, memory_mode=mode).encode()).hexdigest()
           for mode in ("worldmodel", "logbook", "wmlite", "direct")}
    check_pin("chassis_prompt_hashes.json", json.dumps(out, indent=1, sort_keys=True))


def test_chassis_mfm_mode(tmp_path: Path):
    """The mfm arm: the logbook arm's log byte for byte, plus the store beside it."""
    agent, actions = drive_chassis(tmp_path, "mfm")
    ws = agent.memory.root
    pinned_log = (Path(__file__).parent / "pins" / "chassis_logbook_logs.txt").read_text()
    assert _norm((ws / "logs.txt").read_text(), tmp_path) == pinned_log
    pinned_actions = (Path(__file__).parent / "pins" / "chassis_logbook_actions.json").read_text()
    assert json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in a.items()}
                       for a in actions], sort_keys=True) == pinned_actions
    agents_md = (ws / "AGENTS.md").read_text()
    assert "tools/episodes.py" in agents_md and "no earlier frame is kept" not in agents_md
    assert "tools/episodes.py" in agent.codex.prompts[0]   # the turn prompt (retries send the nudge)
    assert (ws / "tools" / "episodes.py").exists() and (ws / "tools" / "zoom.py").exists()
    rows = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines() if l]
    sections = pinned_log.count("\nAction ") - 1          # minus the initial section
    assert len(rows) == sections + 1, (len(rows), sections)  # plus ep_000000
    assert rows[0]["kind"] == "initial" and all(r["kind"] == "episode" for r in rows[1:])
    kinds = [r["action_kind"] for r in rows[1:]]
    assert "dig_down" in kinds and "forward+jump" in kinds
    for r in rows[1:]:
        d = ws / r["path"]
        assert (d / "observation" / "image.png").exists() and (d / "action.json").exists()
        assert (d / "outcome.json").exists() and (d / "state" / "ticks.jsonl").exists()
    # The observation image is the frame the entry opened on, not the latest view.
    import hashlib
    imgs = [hashlib.sha256((ws / r["path"] / "observation" / "image.png").read_bytes()).hexdigest()
            for r in rows]
    assert len(set(imgs)) > 1
    outcome = json.loads((ws / rows[3]["path"] / "outcome.json").read_text())
    assert "moved" in outcome and "events" in outcome and "inventory_delta" in outcome
    rep = agent.report()
    assert rep["memory_mode"] == "mfm" and rep["mfm"]["n"] == len(rows)
    check_pin("chassis_mfm_index.jsonl", _norm((ws / "index.jsonl").read_text(), tmp_path))
    check_pin("chassis_mfm_agents.md", _norm(agents_md, tmp_path))
