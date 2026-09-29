"""Slice 2: the plan-level stall watchdog (harness, every arm) and the mfm arm's
options expect and frames. The watchdog exists because every loop a
chain of lives lost steps to was made of labels the per-label governor never vetoes
(equip_hotbar, close_inventory, craft, use_until_gui, gui clicks, raw holds)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest



# ---------------- governor.check_plan ----------------

def _gov():
    from mcu_worldmodel.governor import Governor
    return Governor()


def _null(g, label, cell, step):
    return g.note_entry(label=label, cell=cell, step=step, events=0, moved=0.0,
                        descended=0.0, inv_changed=False, item_types=set(), milestones=0)


def test_watchdog_refuses_a_stationary_plan_after_four_nulls_of_any_label():
    g = _gov()
    cell = (0, 8, 0)
    for i, label in enumerate(["equip_hotbar", "close_inventory", "craft", "use_until_gui"]):
        _null(g, label, cell, 100 + 10 * i)
    plan = [{"procedure": "equip_hotbar", "args": {"slot": 9}},
            {"procedure": "craft", "args": {"item": "furnace"}}]
    v = g.check_plan(plan, cell, 150, gui_open=False)
    assert v and "STALLED at this spot -- 4 entries in a row" in v and "equip_hotbar, craft" in v
    assert g.plan_stalls == 1
    # a plan that moves, or opens a screen, runs
    assert g.check_plan(plan + [{"procedure": "go_to", "args": {"x": 1, "z": 1}}], cell, 150, False) is None
    assert g.check_plan([{"procedure": "use_until_gui", "args": {"item": "furnace"}}], cell, 150, False) is None
    assert g.check_plan([{"action": {"forward": 1}, "repeat": 20}], cell, 150, False) is None
    # a screen open exempts GUI work (the clock keeps running)
    assert g.check_plan(plan, cell, 150, gui_open=True) is None
    # another cell is another clock
    assert g.check_plan(plan, (1, 8, 0), 150, False) is None


def test_watchdog_stall_clock_and_the_objective_switch():
    g = _gov()
    cell = (3, 8, 3)
    _null(g, "look_abs", cell, 1000)
    plan = [{"procedure": "look_abs", "args": {"pitch": 0}}]
    assert g.check_plan(plan, cell, 1500, False) is None          # 500 steps: not yet
    v = g.check_plan(plan, cell, 1650, False)                      # 650 steps at the cell
    assert v and "650 steps (since step 1000)" in v and "change the OBJECTIVE" not in v
    v = g.check_plan(plan, cell, 2300, False)
    assert v and "change the OBJECTIVE" in v
    # a productive entry resets both the streak and the clock
    g.note_entry(label="craft", cell=cell, step=2310, events=1, moved=0.0, descended=0.0,
                 inv_changed=True, item_types={"furnace"}, milestones=0)
    assert g.check_plan(plan, cell, 2320, False) is None


def test_watchdog_aspiration_clears_the_streak_on_a_milestone():
    g = _gov()
    cell = (0, 8, 0)
    for i in range(4):
        _null(g, "raw", cell, 10 * i)
    assert g.check_plan([{"action": {"attack": 1}, "repeat": 6}], cell, 50, False)
    g.note_entry(label="raw", cell=cell, step=60, events=0, moved=0.0, descended=0.0,
                 inv_changed=False, item_types=set(), milestones=1)      # a milestone
    assert g.check_plan([{"action": {"attack": 1}, "repeat": 6}], cell, 61, False) is None


def test_agent_drops_a_stalled_plan_with_the_maps_hint(tmp_path: Path):
    """A model that rotates null labels at one spot (the furnace loop) is
    refused after four, with the map's hint; a plan that moves runs."""
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.testing import FakeCodex, fake_info
    from test_pins_chassis import _pov
    cfg = [{"event": "craft_item", "identity": "iron_pickaxe", "objects": ["iron_pickaxe"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=tmp_path / "ws", task_text="pickaxe",
                            ledger=MilestoneLedger(cfg, "t"),
                            step_cap=50, memory_mode="logbook", platform_prompt="HOST")
    loop = [{"procedure": "equip_hotbar", "args": {"slot": 9}},
            {"procedure": "close_inventory", "args": {}},
            {"procedure": "look_abs", "args": {"pitch": 10.0, "ticks": 4}},
            {"procedure": "equip_hotbar", "args": {"slot": 8}}]
    script = ([{"actions": {"actions": [e]}, "message": f"[PLAN]\nfiddle {i}"}
               for i, e in enumerate(loop * 2)]
              + [{"actions": {"actions": [{"action": {"forward": 1, "jump": 1}, "repeat": 8}]},
                  "message": "[PLAN]\nmove"}] * 6)
    agent.codex = FakeCodex(agent.memory.root, script)
    info = fake_info(inventory={"cobblestone": 8, "furnace": 1})
    info["pov"] = _pov(0)
    agent.start(info)
    # the avatar walked a few cells before settling here (so the map has a hint)
    for step in range(1, 12):
        info["location_stats"]["xpos"] = np.array(1.0 + 0.6 * step)
        agent.observe(info, step)
    for step in range(12, 160):
        agent.next_action(info)
        info["pov"] = _pov(step)
        agent.observe(info, step)
    assert agent.cursor_stats.get("governor_plan_stalls", 0) >= 1
    log = (agent.memory.root / "logs.txt").read_text()
    assert "governor: STALLED at this spot" in log and "The map: you walked cell" in log
    assert agent.report()["watchdog"]["plan_stalls"] == agent.cursor_stats["governor_plan_stalls"]


# ---------------- the mfm options ----------------

def test_expect_option_echoes_the_line_against_the_record(tmp_path: Path):
    import pytest
    from test_pins_chassis import drive_chassis
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "x", "logbook", expect=True)
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "briefing one\nEXPECT: moved about 1 block east\n[PLAN]\nwalk"},
        {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 3}]},
         "message": "OBSERVED vs EXPECTED: matched\n[PLAN]\nchop"},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
          "message": f"[PLAN]\nchop {i}\nEXPECT: a log"} for i in range(10)]
    agent, _ = drive_chassis(tmp_path, "mfm", steps=60, script=script, expect=True)
    prompts = agent.codex.prompts
    assert "[EXPECTED]" not in prompts[0]
    second = next(p for p in prompts[1:] if "[EXPECTED]" in p)
    assert "[EXPECTED] moved about 1 block east" in second
    assert "[OBSERVED] by the harness for that plan (each entry with the frame it started from):" in second
    assert "one visible change" in second          # VISTA's observe step
    assert "forward" in second.split("[OBSERVED]")[1].split("Begin your briefing")[0]
    assert "OBSERVED vs EXPECTED" in second
    # a briefing without the line is said so
    third = [p for p in prompts if "no `EXPECT:` line" in p]
    assert third, "the missing EXPECT line was not flagged"
    agents_md = (agent.memory.root / "AGENTS.md").read_text()
    assert "Expect, then compare" in agents_md
    assert agent.report()["mfm_options"] == {"expect": True, "frames": False, "event_sheet": True}
    assert agent.cursor_stats["expect_lines"] >= 2


def test_frames_option_writes_zoom_and_says_so(tmp_path: Path):
    from test_pins_chassis import drive_chassis
    agent, _ = drive_chassis(tmp_path, "mfm", steps=40, frames=True)
    ws = agent.memory.root
    assert (ws / "tools" / "zoom.py").exists() and (ws / "tools" / "episodes.py").exists()
    agents_md = (ws / "AGENTS.md").read_text()
    assert "zoom.py" in agents_md and "2x2 sheet" in agents_md
    # the base mfm arm is untouched: no zoom, no mention
    agent2, _ = drive_chassis(tmp_path / "base", "mfm", steps=40)
    assert not (agent2.memory.root / "tools" / "zoom.py").exists()
    assert "zoom" not in (agent2.memory.root / "AGENTS.md").read_text()


def test_frame_size_flag_reaches_the_agent():
    from worldmodel_purple_agent import WorldModelExecutor
    ex = WorldModelExecutor(workspace_root=Path("/tmp/does-not-matter-wm"), model="m",
                            codex_home=None, memory_mode="mfm", frame_size=(320, 180))
    assert ex.frame_size == (320, 180) and ex.memory_mode == "mfm"


@pytest.mark.parametrize("arm", ["mfm", "mfm-matched"])
def test_the_executor_builds_a_life_that_carries_an_earlier_one(tmp_path, arm):
    """`--seed-memory` through the purple agent's own constructor path: the agent is
    built, the earlier life is under previous/, and the life can start."""
    from mcu_worldmodel.arms import ARMS
    from mcu_worldmodel.testing import fake_info
    from test_pins_chassis import drive_chassis
    from worldmodel_purple_agent import WorldModelExecutor

    first, _ = drive_chassis(tmp_path / "first", "mfm", steps=40, **ARMS[arm])
    ex = WorldModelExecutor(workspace_root=tmp_path / "second", model="m", codex_home=None,
                            memory_mode=arm, seed_memory=[str(first.memory.root)])
    ex._episode, ex._task_text = 1, "get a log"
    ex._workspace = ex.workspace_root / "episode_001"
    info = fake_info(inventory={})
    ex._build_agent(info)
    root = ex._agent.memory.root
    assert (root / "previous" / "life_1" / "logs.txt").exists()
    assert (root / "previous" / "index.jsonl").read_text().strip()
    ex._agent.start(info)
    assert (root / "AGENTS.md").exists()
