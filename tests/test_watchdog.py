"""Slice 2: the plan-level stall watchdog (harness, every arm) and the mfm arm's
options --expect, --frames, --corridors. The watchdog exists because every loop the
2026-09-06 chain lost steps to was made of labels the per-label governor never vetoes
(equip_hotbar, close_inventory, craft, use_until_gui, gui clicks, raw holds)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from conftest import check_pin


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
    """A model that rotates null labels at one spot (the obf1 furnace loop) is
    refused after four, with the map's hint; a plan that moves runs."""
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import FakeCodex, fake_info
    from test_pins_chassis import _pov
    cfg = [{"event": "craft_item", "identity": "iron_pickaxe", "objects": ["iron_pickaxe"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=tmp_path / "ws", task_text="pickaxe",
                            ledger=MilestoneLedger(cfg, "t"), induction_every=10,
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
    assert "one visible change" in second          # VISTA's observe step, 2026-09-08
    assert "forward" in second.split("[OBSERVED]")[1].split("Begin your briefing")[0]
    assert "OBSERVED vs EXPECTED" in second
    # a briefing without the line is said so
    third = [p for p in prompts if "no `EXPECT:` line" in p]
    assert third, "the missing EXPECT line was not flagged"
    agents_md = (agent.memory.root / "AGENTS.md").read_text()
    assert "Expect, then compare" in agents_md
    assert agent.report()["mfm_options"] == {"expect": True, "frames": False, "corridors": False,
                                              "sites": False, "event_sheet": True}
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


def _life_log(y_low: float = 11.0) -> str:
    """A logs.txt with a dry corridor at y 11 (steps 500-560), a lava sighting after
    it, and a pond fill at the surface."""
    secs = ["=" * 80 + "\nAction 0 | Step 0 | INITIAL STATE\n\nTask: x\n"
            "[STATE] pos=(0.50, 71.00, 0.50) pitch=0 yaw=0 moved=0.00\n"]
    n = 1
    secs.append("=" * 80 + f"\nAction {n} | Step 100 | Plan Step 1/2\n\n[ACTION] fill_bucket() -> 40 ticks\n"
                "[STATE] pos=(3.50, 70.00, 2.50) pitch=25 yaw=0 moved=3.00\n[INV] bucket -1, water_bucket +1\n"
                "[NOTE] fill_bucket: the bucket filled -- water_bucket +1 (aim 3 of 25, pitch 25 yaw 0, 18 ticks).\n")
    x = 10.0
    for i in range(8):
        n += 1
        secs.append("=" * 80 + f"\nAction {n} | Step {500 + 8 * i} | Plan Step 1/1\n\n"
                    f"[ACTION] mine_forward(n=60) -> 60 ticks\n"
                    f"[STATE] pos=({x + 4 * i:.2f}, {y_low:.2f}, 5.50) pitch=0 yaw=-90 moved=4.00\n")
    n += 1
    secs.append("=" * 80 + f"\nAction {n} | Step 600 | Plan Step 1/1\n\n[ACTION] mine_forward(n=60) -> 60 ticks\n"
                f"[STATE] pos=(44.50, {y_low:.2f}, 5.50) pitch=0 yaw=-90 moved=2.00\n"
                "[NOTE] LAVA AHEAD: 40% of the lower view is lava at (44, 11, 5) facing yaw -90. x\n")
    return "\n".join(secs)


def test_corridors_are_extracted_merged_and_rendered(tmp_path: Path):
    from mcu_worldmodel.previous import (PreviousLives, corridors_from_log, merge_corridors,
                                         MFM_CORRIDOR_NOTE)
    cs = corridors_from_log(_life_log(), 1)
    assert len(cs) == 1
    c = cs[0]
    assert c.a == (10, 11, 6) and c.b == (38, 11, 6) and c.step0 == 500 and c.step1 == 556
    assert c.length == 28.0 and c.sections == 8
    # a shallow run is not a corridor; a duplicate line merges away
    assert corridors_from_log(_life_log(y_low=40.0), 1) == []
    assert len(merge_corridors(cs + corridors_from_log(_life_log(), 2))) == 1
    # a seeded workspace renders it when a deep milestone is open
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "logs.txt").write_text(_life_log())
    (seed / "index.jsonl").write_text(json.dumps({
        "id": "ep_000009", "first_step": 596, "last_step": 660, "kind": "episode",
        "image": "episodes/ep_000009/observation/image.png", "path": "episodes/ep_000009"}) + "\n")
    ws = tmp_path / "ws"
    ws.mkdir()
    pl = PreviousLives(ws)
    pl.seed([seed])
    assert len(pl.corridors) == 1 and pl.sites
    pos = {"x": 12.0, "y": 11.0, "z": 5.0}
    plain = pl.block(pos, {"water_bucket": 1}, {"mine_obsidian"})
    assert "DRY CORRIDOR" not in plain and "frame=" not in plain
    rich = pl.block(pos, {"water_bucket": 1}, {"mine_obsidian"}, frames=True, corridors=True)
    assert "DRY CORRIDOR: life 1 tunnelled from (10, 11, 6) to (38, 11, 6)" in rich
    assert "steps 500-556, 28 blocks over 8 entries" in rich
    assert "frame=previous/life_1/episodes/ep_000009/observation/image.png" in rich
    assert "re-digging that line is safe" in rich
    # nothing deep open: sites only
    assert "DRY CORRIDOR" not in pl.block(pos, {}, {"kill_ender_dragon"}, corridors=True)
    assert "DRY CORRIDORS" in MFM_CORRIDOR_NOTE
    audit = json.loads((ws / "previous" / "sites.json").read_text())
    assert audit["corridors"][0]["length"] == 28.0


def test_frame_size_flag_reaches_the_agent():
    from worldmodel_purple_agent import WorldModelExecutor
    ex = WorldModelExecutor(workspace_root=Path("/tmp/does-not-matter-wm"), model="m",
                            codex_home=None, memory_mode="mfm", frame_size=(320, 180),
                            expect=True, frames=True, corridors=True)
    assert ex.frame_size == (320, 180) and ex.expect and ex.frames and ex.corridors
