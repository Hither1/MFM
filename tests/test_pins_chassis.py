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


def drive_chassis(root: Path, memory_mode: str, steps: int = 120, **kw):
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
                            platform_prompt="HOST REFERENCE", **kw)
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
    assert (ws / "tools" / "episodes.py").exists() and not (ws / "tools" / "zoom.py").exists()
    assert "zoom" not in agents_md and "crops" not in agents_md
    assert not list(ws.glob("episodes/*/observation/crops"))
    rows = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines() if l]
    sections = pinned_log.count("\nAction ") - 1          # minus the initial section
    assert len(rows) == sections + 1, (len(rows), sections)  # plus ep_000000
    assert rows[0]["kind"] == "initial" and all(r["kind"] == "episode" for r in rows[1:])
    kinds = [r["action_kind"] for r in rows[1:]]
    assert "dig_down" in kinds and "forward+jump" in kinds
    for r in rows[1:]:
        d = ws / r["path"]
        assert (d / "observation" / "image.png").exists() and (d / "action.json").exists()
        assert (d / "outcome.json").exists() and not (d / "state" / "ticks.jsonl").exists()
    # The observation image is the frame the entry opened on, not the latest view.
    import hashlib
    imgs = [hashlib.sha256((ws / r["path"] / "observation" / "image.png").read_bytes()).hexdigest()
            for r in rows]
    assert len(set(imgs)) > 1
    outcome = json.loads((ws / rows[3]["path"] / "outcome.json").read_text())
    assert "moved" in outcome and "events" in outcome and "inventory_delta" in outcome
    rep = agent.report()
    assert rep["memory_mode"] == "mfm" and rep["mfm"]["n"] == len(rows)
    assert "hypotheses" not in rep and "discipline" not in rep     # the structured arm's, always zero here
    check_pin("chassis_mfm_index.jsonl", _norm((ws / "index.jsonl").read_text(), tmp_path))
    check_pin("chassis_mfm_agents.md", _norm(agents_md, tmp_path))


def test_chassis_mfm_retrieval(tmp_path: Path):
    """`--retrieval`: the mfm arm with the [RECALL] block in its turn prompt. The log
    and the actions are still the logbook arm's byte for byte; the contract gains the
    paragraph that names the block; the block appears once the scripted chops (20
    `attack x6` entries that change nothing) form a streak, and it is pinned."""
    import pytest
    from mcu_worldmodel.agent import WorldModelAgent
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "x", "logbook", retrieval=True)
    agent, actions = drive_chassis(tmp_path, "mfm", retrieval=True)
    ws = agent.memory.root
    pinned_log = (Path(__file__).parent / "pins" / "chassis_logbook_logs.txt").read_text()
    assert _norm((ws / "logs.txt").read_text(), tmp_path) == pinned_log
    pinned_actions = (Path(__file__).parent / "pins" / "chassis_logbook_actions.json").read_text()
    assert json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in a.items()}
                       for a in actions], sort_keys=True) == pinned_actions
    agents_md = (ws / "AGENTS.md").read_text()
    base_md = (Path(__file__).parent / "pins" / "chassis_mfm_agents.md").read_text()
    assert "[RECALL]" in agents_md and "[RECALL]" not in base_md
    from mcu_worldmodel.episodes import MFM_RETRIEVAL_NOTE
    assert _norm(agents_md, tmp_path).replace("\n\n" + MFM_RETRIEVAL_NOTE, "") == base_md
    prompts = agent.codex.prompts
    with_block = [p for p in prompts if "[RECALL]" in p]
    assert with_block, "no turn prompt carried the block"
    # The first prompts have no streak yet and read exactly as the flag-off arm's.
    assert "[RECALL]" not in prompts[0]
    last = with_block[-1]
    assert "`attack` changed nothing in its last" in last
    assert "It last changed something at step" in last     # the chop that mined the log
    assert "Milestones so far" in last and "mine_log step" in last
    assert last.index("[RECALL]") < last.index("Your memory is `./logs.txt`")
    rep = agent.report()
    assert rep["mfm"]["retrieval"] is True and rep["mfm"]["recalls"] == len(with_block)
    check_pin("chassis_mfm_recall_prompt.txt", _norm(last, tmp_path))


def test_chassis_vision_audit_survives_a_real_rollout(tmp_path: Path):
    """`report()` must not raise on the real backend.

    The pin tests above drive the agent with the selftest's FakeCodex, whose
    `vision_audit` is a fixed dict, so an audit key the real backend cannot produce is
    invisible to them. One did happen: `vision_audit` read a key that the rollout scan
    did not write, every `save_report` raised KeyError inside the adapter's
    `try/except`, and the whole wave finished with no report at all.
    """
    from mcu_worldmodel.codex_backend import CodexTurn

    home = tmp_path / "home"
    sid = "01a06fad-0685-71d1-afa7-ce20e9d9f3f2"
    day = home / "sessions" / "2026" / "09" / "04"
    day.mkdir(parents=True)
    (day / f"rollout-2026-09-04T23-46-45-{sid}.jsonl").write_text(
        '{"type":"thread.started","thread_id":"%s"}\n'
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"./tools/episodes.py --last 5"}}\n'
        '{"type":"custom_tool_call","name":"view_image"}\n' % sid, encoding="utf-8")

    ws = tmp_path / "ws"
    ws.mkdir()
    codex = CodexTurn(ws, model="gpt-5.6-sol", codex_home=home)
    codex.session_id = sid
    audit = codex.vision_audit()
    for key in ("frames_attached", "view_image_calls", "image_attach_failures",
                "tool_errors", "turns_with_tool_error", "episodes_tool_calls",
                "compactions", "session_max_turns" if False else "empty_resets"):
        assert key in audit, key
    assert audit["episodes_tool_calls"] == 1, audit["episodes_tool_calls"]
    assert audit["view_image_calls"] == 1, audit["view_image_calls"]


def test_episodes_tool_counted_in_every_cli_shape(tmp_path: Path):
    """The counter must see a call in each shape a CLI records one in, and must not
    count the tool's own description in the system prompt.

    Both shapes are taken from real runs: codex 0.149 records shell work as
    `command_execution` (MCU's saved transcripts), 0.153 runs it in a code-mode `exec`
    cell recorded as `custom_tool_call` (the KiCad GPT-6 rollouts). Counting only the
    first pair reported 0 for a KiCad run whose 1,410 exec cells were the only place a
    call could appear, and 0 for an MCU run whose transcripts hold 18 real calls.
    """
    from mcu_worldmodel import codex_backend as chassis
    from mfm.backend import codex_turn as shared

    f = tmp_path / "turn_0001.events.jsonl"
    f.write_text(
        # the system prompt describing the tool: NOT a call
        '{"type":"response_item","payload":{"type":"message","content":'
        '"`./tools/episodes.py --last 5` lists matching episodes"}}\n'
        # codex 0.149, MCU
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"/usr/bin/bash -lc \\"./tools/episodes.py --last 8\\""}}\n'
        # codex 0.153, KiCad code mode
        '{"type":"response_item","payload":{"type":"custom_tool_call","name":"exec",'
        '"input":"{\\"command\\":\\"./tools/episodes.py --tag stuck\\"}"}}\n'
        # the older direct shape
        '{"type":"response_item","payload":{"type":"function_call","name":"shell",'
        '"arguments":"{\\"command\\":[\\"bash\\",\\"-lc\\",\\"./tools/episodes.py --near 1 2\\"]}"}}\n',
        encoding="utf-8")
    for mod in (shared, chassis):
        n = mod.count_episodes_tool(f, mod._ROLLOUT_EPISODES_TOOL)
        assert n == 3, f"{mod.__name__} counted {n}, expected 3 (one per call shape)"

    # And the whole-file scanners agree, without counting the description.
    assert shared.scan_rollout_full(f)["episodes_tool_calls"] == 3
    assert chassis.scan_rollout(f)["episodes_tool_calls"] == 3


def test_episodes_tool_falls_back_to_the_transcripts(tmp_path: Path):
    """A codex home that did not survive the run (MCU's is node-local /var/tmp) leaves
    no rollout to scan; the backend's own saved turn events still carry the calls."""
    from mcu_worldmodel.codex_backend import CodexTurn

    home = tmp_path / "home"
    sid = "01a06fad-0685-71d1-afa7-ce20e9d9f3f2"
    day = home / "sessions" / "2026" / "09" / "05"
    day.mkdir(parents=True)
    (day / f"rollout-x-{sid}.jsonl").write_text(
        '{"type":"thread.started","thread_id":"%s"}\n' % sid, encoding="utf-8")
    tdir = tmp_path / "codex_turns"
    tdir.mkdir()
    (tdir / "turn_0001.events.jsonl").write_text(
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"bash -lc ./tools/episodes.py --last 8"}}\n', encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    codex = CodexTurn(ws, model="gpt-5.6-sol", codex_home=home, transcript_dir=tdir)
    codex.session_id = sid
    assert codex.vision_audit()["episodes_tool_calls"] == 1
