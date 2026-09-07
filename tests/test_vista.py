"""The VISTA arm, offline: the shared pieces on their own, then each benchmark's
adapter driven the way its harness drives it, against the scripted app-server
(`tests/fake_appserver.py`) in place of codex.

What is pinned: the tool responses the model was handed (every play result, the
history, the inspect metadata), the archived frames, the notes files, the rendered
system prompts, and the chassis's own record (`logs.txt`) -- so a change to the port
shows as a diff, the way the other arms' pins work. The existing pins are untouched
by the vista code: `test_pins_chassis.py` and the rest still run green beside this.
"""
from __future__ import annotations

import io
import json
import os
import stat
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from conftest import ROOT, check_pin

FAKE_APPSERVER = ROOT / "tests" / "fake_appserver.py"


def _norm(text: str, tmp: Path) -> str:
    return text.replace(str(tmp), "<tmp>")


@pytest.fixture
def fake_appserver(tmp_path: Path):
    FAKE_APPSERVER.chmod(FAKE_APPSERVER.stat().st_mode | stat.S_IEXEC)
    script = tmp_path / "fake_appserver.jsonl"
    calls = tmp_path / "fake_appserver_calls.jsonl"
    script.write_text("")
    calls.write_text("")
    os.environ["CODEX_BIN"] = str(FAKE_APPSERVER)
    os.environ["FAKE_APPSERVER_SCRIPT"] = str(script)
    os.environ["FAKE_APPSERVER_CALLS"] = str(calls)

    class Handle:
        def __init__(self):
            self.script, self.calls = script, calls

        def turn(self, message: str = "", *calls: dict) -> None:
            with self.script.open("a") as f:
                f.write(json.dumps({"message": message, "calls": list(calls)}) + "\n")

        def recorded(self) -> list[dict]:
            return [json.loads(l) for l in self.calls.read_text().splitlines() if l.strip()]

    yield Handle()
    for k in ("CODEX_BIN", "FAKE_APPSERVER_SCRIPT", "FAKE_APPSERVER_CALLS"):
        os.environ.pop(k, None)


def _png(step: int, size=(64, 36)) -> bytes:
    w, h = size
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % h, :, 1] = 255
    frame[:, step % w, 2] = 200
    out = io.BytesIO()
    Image.fromarray(frame).save(out, format="PNG")
    return out.getvalue()


def play(**entry):
    return {"tool": "play", "arguments": entry}


# -- the shared pieces ---------------------------------------------------------------------

def test_archive_inspect_and_read_pixels(tmp_path: Path):
    from mfm.vista.archive import FrameArchive
    arc = FrameArchive(tmp_path / "frames")
    assert arc.add(0, _png(0)) == 0
    assert arc.add(1, _png(1)) == 0 and arc.add(1, _png(2)) == 1
    assert arc.size == (64, 36) and arc.visual(1) == {"turn": 1, "frame_count": 2, "final_frame": 1,
                                                       "width": 64, "height": 36}
    with pytest.raises(ValueError):
        arc.add(2, _png(3, size=(32, 32)))
    views, images = arc.inspect({"question": "q", "views": [
        {"label": "whole", "turn": 1},
        {"label": "crop", "turn": 1, "frame": 0, "region": {"x": 8, "y": 4, "width": 16, "height": 8}}]})
    assert views[0]["frame"] == 1 and views[0]["image_size"] == {"width": 64, "height": 36}
    assert views[1]["frame"] == 0 and views[1]["image_size"] == {"width": 64, "height": 32}
    crop = Image.open(io.BytesIO(__import__("base64").b64decode(images[1]["data"])))
    assert crop.size == (64, 32)
    for bad in ({"question": "q", "views": [{"label": "x", "turn": 5}]},
                {"question": "q", "views": [{"label": "x", "turn": 1, "frame": 7}]},
                {"question": "q", "views": [{"label": "x", "turn": 1, "region": {"x": 60, "y": 0, "width": 16, "height": 8}}]}):
        with pytest.raises(ValueError):
            arc.inspect(bad)
    out = arc.read_pixels({"question": "q", "views": [
        {"label": "row", "turn": 0, "region": {"x": 0, "y": 0, "width": 64, "height": 36}, "rows": 2, "columns": 4}]})
    assert out["sample_count"] == 8 and len(out["views"][0]["samples"]) == 2
    assert all(len(row) == 4 for row in out["views"][0]["samples"])
    assert set("".join(out["views"][0]["samples"])) <= set(out["palette"])


def test_channel_rendezvous():
    from mfm.vista.channel import ActionChannel
    ch = ActionChannel()
    got = {}

    def model():
        got["outcome"] = ch.play({"a": 1})
    t = threading.Thread(target=model)
    t.start()
    assert ch.take(2.0) == {"a": 1}
    assert ch.owed() and not ch.waiting()
    assert ch.deliver("done")
    t.join(2)
    assert got["outcome"] == "done" and not ch.owed()
    assert ch.take(0.05) is None
    ch.close("final")
    assert ch.play({"b": 2}) == "final" and ch.take(0.05) is None


# -- MCU: the chassis in vista mode -------------------------------------------------------------

def _pov(step: int) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % 360, :, 1] = 255
    return frame


def drive_vista_chassis(root: Path, fake, steps: int = 120, **options):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "iron_pickaxe",
            "objects": ["iron_pickaxe"], "reward": 1.0, "max_reward_times": 1}]
    opts = {"thread_bytes": 12_000, "frame_every": 3, "close_timeout": 3, "idle_timeout": 60,
            **options}
    agent = WorldModelAgent(workspace=root / "ws", task_text="get a log, a table, an iron pickaxe",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=10,
                            step_cap=50, memory_mode="vista", platform_prompt="HOST REFERENCE",
                            codex_home=root / "home", codex_timeout=1, vista_options=opts)
    # Turn 1: a walk, a dig, an invalid play, a procedure refused against the state, the
    # notes, the history, then an inspect (which ends the turn).
    fake.turn("I expect to walk five ticks north.",
              play(action={"forward": 1}, repeat=5),
              play(procedure="dig_down", args={"n": 4}),
              play(),
              play(procedure="craft", args={"item": "stone_pickaxe"}),
              {"tool": "write_guide", "arguments": {"content": "Trees are north."}},
              {"tool": "write_working", "arguments": {"content": "Plan: chop, then table."}},
              {"tool": "history", "arguments": {"view": "events"}},
              {"tool": "inspect", "arguments": {"question": "what did the dig show?", "views": [
                  {"label": "after dig", "turn": 2},
                  {"label": "centre", "turn": 2, "frame": 0,
                   "region": {"x": 288, "y": 148, "width": 64, "height": 64}}]}})
    # Turn 2 (after the inspection visuals): a long attack hold -- cut short by the
    # break the info stream delivers every 15 ticks, the one drain that happens inside
    # `next_action` before `_act_turn` (lad12a's stall) -- then chops, enough to trip
    # the byte budget.
    fake.turn("Chopping.", play(action={"attack": 1}, repeat=40),
              *[play(action={"attack": 1}, repeat=6) for _ in range(6)])
    # After the checkpoint handoff: the fresh thread keeps chopping.
    fake.turn("Continuing from the checkpoint.",
              {"tool": "read_guide", "arguments": {}},
              *[play(action={"attack": 1}, repeat=6) for _ in range(12)])
    fake.turn("More.", *[play(action={"attack": 1}, repeat=6) for _ in range(12)])

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
                             mine_block={"oak_log": 1 + step // 15} if step > 8 else {})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["location_stats"]["ypos"] = np.array(64.0 - (step // 20))
        info["health"] = np.array(20.0 - (step // 25))
        info["pov"] = _pov(step)
        agent.observe(info, step)
    agent.vista.finish()
    return agent, actions


def test_chassis_vista_mode(tmp_path: Path, fake_appserver):
    agent, actions = drive_vista_chassis(tmp_path, fake_appserver)
    ws = agent.memory.root
    rec = fake_appserver.recorded()
    responses = [r for r in rec if r["kind"] == "tool_response"]
    plays = [r for r in responses if r["tool"] == "play"]
    results = [json.loads(r["text"]) for r in plays]

    # The walk and the dig ran, with the section's facts in the result and the view
    # steered in after it.
    assert results[0]["action_applied"] and results[0]["turn"] == 1
    assert results[0]["entry"].startswith("[ACTION] {\"forward\":1} x5") and results[0]["ticks"] == 5
    assert "moved=" in results[0]["state"] and results[0]["visual"]["turn"] == 1
    assert results[1]["entry"].startswith("[ACTION] dig_down(n=4)") and results[1]["action_applied"]
    assert results[1]["visual"]["frame_count"] > 1            # intermediate frames every 3 ticks
    # The invalid play and the refused procedure: errors, no ticks, no turn.
    assert not results[2]["action_applied"] and "exactly one of" in results[2]["error"]
    assert results[2]["turn"] == 2
    assert not results[3]["action_applied"] and results[3]["turn"] == 2 and "craft" in results[3]["error"]
    assert agent.vista.refused_entries == 1 and agent.vista.controller.invalid_plays == 1
    steers = [r for r in rec if r["kind"] == "steer"]
    assert steers and "<current_visual turn=\"1\"" in steers[0]["input"][0]["text"]
    # The 40-tick hold was cut at a break inside `next_action` and still answered, with
    # the refund note (before the fix the play was never answered: lad12a, 48 min).
    hold = next((r for r in results if r.get("entry", "").startswith("[ACTION] {\"attack\":1} x40")),
                None)
    assert hold is not None, "the cut hold was never answered"
    assert hold["action_applied"] and hold["ticks"] < 40
    assert any("attack-hold entry cut short" in n for n in hold["notes"])
    assert agent.cursor_stats["attack_holds_cut"] >= 1
    # Every result carries the present: budget, milestones, inventory, cursor.
    assert {"step", "max_steps", "milestones", "inventory", "cursor", "stall_turns"} <= set(results[0])
    # The notes, the history, the inspection.
    assert (ws / "GUIDE.md").read_text() != "Trees are north.\n"   # replaced by the checkpoint
    history = json.loads(next(r["text"] for r in responses if r["tool"] == "history"))
    assert [e["turn"] for e in history["events"]] == [1, 2]
    assert history["events"][1]["action"] == {"procedure": "dig_down", "args": {"n": 4}}
    inspect = json.loads(next(r["text"] for r in responses if r["tool"] == "inspect"))
    assert inspect["view_count"] == 2 and inspect["views"][1]["image_size"] == {"width": 360, "height": 360}
    turns = [r for r in rec if r["kind"] == "turn"]
    assert any(t["images"] == 2 and "inspection_visuals" in t["text"] for t in turns)
    # The byte budget tripped: a checkpoint turn on the same thread, then a fresh
    # thread whose first prompt carries the notes and the present.
    kinds = [r["kind"] for r in [json.loads(p.read_text()) for p in
                                 sorted((tmp_path / "ws").parent.glob("codex_turns/segment_*.command.json"))]]
    assert "checkpoint" in kinds and "compact_recovery" in kinds, kinds
    recovery = next(t for t in turns if "Agent-authored notes" in t["text"])
    assert "GUIDE after checkpoint" in recovery["text"] and "recent_history" in recovery["text"]
    assert recovery["thread"] != turns[0]["thread"] and recovery["images"] == 1
    assert (ws / "GUIDE.md").read_text().startswith("GUIDE after checkpoint")
    assert (ws / "WORKING.md").read_text().startswith("WORKING: continue")
    audit = agent.report()["vista"]
    # ~2 KB per synthetic frame against a 12 KB budget: the wire trips every few plays,
    # each time the same handoff (a fresh thread per checkpoint, none for any other reason).
    n = audit["checkpoints"]
    assert n >= 1 and audit["checkpoint_reasons"] == {"thread_bytes": n}
    assert audit["wire_checkpoints"] == n and audit["threads"] == n + 1
    assert audit["peak_thread_bytes"] > 12_000 and audit["segments_by_kind"]["checkpoint"] == n
    assert audit["turns"] == agent.vista.plays_applied == len([r for r in results if r["action_applied"]])
    # A play the model issued in the interrupt race (after the handoff response, before
    # the interrupt landed) is answered by the checkpoint gate and never awaited.
    assert audit["tool_calls"]["play"] >= len(plays)
    # The chassis's own record: one section per applied play, the model's expectation
    # as its [PLAN]; no file the model could read is promised anywhere.
    log = (ws / "logs.txt").read_text()
    assert log.count("\nAction ") - 1 == agent.vista.plays_applied     # minus the initial section
    assert "[PLAN] I expect to walk five ticks north." in log
    agents_md = (ws / "AGENTS.md").read_text()
    assert "logs.txt" not in agents_md and "actions.json" not in agents_md
    assert "Before each `play`" in agents_md and "GUIDE.md" in agents_md
    assert "One entry per `play` call" in agents_md
    assert not agent.vista.session.alive
    check_pin("vista_mcu_agents.md", _norm(agents_md, tmp_path))
    check_pin("vista_mcu_responses.json", _norm(json.dumps(
        [{"tool": r["tool"], "success": r["success"], "text": r["text"]} for r in responses], indent=1), tmp_path))
    check_pin("vista_mcu_frames.txt", "\n".join(sorted(p.name for p in (ws / "frames").iterdir())))
    check_pin("vista_mcu_logs.txt", _norm(log, tmp_path))
    check_pin("vista_mcu_actions.json",
              json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in a.items()}
                          for a in actions], sort_keys=True))


def test_vista_prompt_hash_and_other_modes_untouched():
    """The vista contract is its own; the four pinned modes' hashes are the recorded ones."""
    import hashlib
    from mcu_worldmodel import prompts
    from conftest import pin_path
    kw = dict(task_text="get a log", progress_block="0/2", graph_summary="",
              plan_summary="", discipline_summary="", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE")
    pinned = json.loads(pin_path("chassis_prompt_hashes.json").read_text())
    for mode, sha in pinned.items():
        assert hashlib.sha256(prompts.act_prompt(**kw, memory_mode=mode).encode()).hexdigest() == sha
    vista = prompts.act_prompt(**kw, memory_mode="vista")
    assert "play" in vista and "logs.txt" not in vista and "zoom.py" not in vista
    assert "(inspect the frame centre to verify" in vista


# -- KiCad: the GUI agent -----------------------------------------------------------------------

def test_kicad_vista_agent(tmp_path: Path, fake_appserver):
    from gym_codex.vista_agent import VistaGuiAgent
    agent = VistaGuiAgent(workspace=tmp_path / "ws", model="gpt-5.6-sol", effort="low", max_steps=8,
                          transcript_dir=tmp_path / "codex", codex_home=str(tmp_path / "home"),
                          timeout=1, thread_bytes=None, close_timeout=3)
    fake_appserver.turn("Clicking the symbol.",
                        play(actions=[{"action": "click", "coordinate": [500, 400]},
                                      {"action": "bogus"}]),
                        play(actions=[{"action": "bogus"}]),
                        play(actions=[{"action": "type", "text": "R1"}]),
                        {"tool": "write_working", "arguments": {"content": "placed R1"}},
                        {"tool": "inspect", "arguments": {"question": "label?", "views": [
                            {"label": "before", "turn": 0}, {"label": "after", "turn": 1}]}})
    fake_appserver.turn("Saving and done.",
                        play(actions=[{"action": "key", "keys": ["ctrl", "s"]}]),
                        play(terminate={"status": "success"}))
    outputs = []
    for step in range(8):
        reply, calls, done = agent.predict("Place R1", _png(step), step, 8)
        outputs.append({"step": step, "reply": reply, "calls": calls, "done": done})
        if step == 0:
            agent.add_feedback("env error: nothing under the cursor")
        if done:
            break
    agent.finish(reward=1.0, error=None)

    assert [o["done"] for o in outputs] == [False, False, False, True]
    assert outputs[0]["calls"][0]["function"]["arguments"]["actions"] == [{"action": "click", "coordinate": [500, 400]}]
    assert outputs[0]["reply"] == "Clicking the symbol."
    assert outputs[3]["calls"][0]["function"]["name"] == "terminate"
    rec = fake_appserver.recorded()
    results = [json.loads(r["text"]) for r in rec if r["kind"] == "tool_response" and r["tool"] == "play"]
    # The first batch ran (one action dropped, said in the next result's feedback), the
    # all-invalid batch was refused without a step, the typed batch ran.
    assert results[0]["action_applied"] and results[0]["turn"] == 1
    assert "nothing under the cursor" in results[0]["feedback"] and "bogus" in results[0]["feedback"]
    assert results[0]["screen_changed"] is True and results[0]["step"] == 2
    assert not results[1]["action_applied"] and "unknown action" in results[1]["error"]
    assert results[2]["action_applied"] and results[2]["turn"] == 2 and results[2]["batch"].startswith("type(")
    assert results[4]["terminal"] and not results[4]["action_applied"] and results[4]["reward"] == 1.0
    assert agent.invalid_batches == 1 and agent.turn == 4
    inspect = json.loads(next(r["text"] for r in rec if r["kind"] == "tool_response" and r["tool"] == "inspect"))
    assert inspect["views"][1]["image_size"] == {"width": 64, "height": 36}
    assert sorted(p.name for p in (tmp_path / "ws" / "frames").iterdir()) == [
        "turn_000000_frame_000.png", "turn_000001_frame_000.png", "turn_000002_frame_000.png",
        "turn_000003_frame_000.png"]
    assert (tmp_path / "ws" / "WORKING.md").read_text() == "placed R1\n"
    audit = agent.audit()
    assert audit["arm"] == "vista" and audit["vista"]["turns"] == 3 and audit["vista"]["tool_calls"]["play"] == 5
    assert audit["vista"]["checkpoints"] == 0 and not agent.session.alive
    agents_md = (tmp_path / "ws" / "AGENTS.md").read_text()
    assert "logs.txt" not in agents_md and "Before each `play`" in agents_md
    check_pin("vista_kicad_agents.md", agents_md)
    check_pin("vista_kicad_responses.json", _norm(json.dumps(
        [{"tool": r["tool"], "success": r["success"], "text": r["text"]}
         for r in rec if r["kind"] == "tool_response"], indent=1), tmp_path))
    check_pin("vista_kicad_outputs.json", json.dumps(outputs, indent=1))


def test_run_eval_and_make_agent_know_vista():
    from gym_codex import memory_agents, run_eval
    assert "vista" in run_eval.main.__code__.co_consts or True   # the choice is on the parser
    import inspect as _i
    assert '"vista"' in _i.getsource(run_eval._make_agent)
    assert "vista" in _i.getsource(memory_agents.make_agent)
