"""Head under lava is a view of its own: a flat red that the lava and the flame detectors
both read as nothing. Three lives of one chain swam in the Nether's lava sea while the
harness and the shipped `hit` reflex called the loss a mob's. And `go_to(sneak=true)`: the
walk that took them over the plateau's edge can be told to stop at one."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from mcu_worldmodel import procedures as P, skills, vision

DATA = Path(__file__).parent / "data" / "lava_submerged"


def _frame(name: str) -> np.ndarray:
    return np.asarray(Image.open(DATA / f"{name}.png").convert("RGB"))


@pytest.mark.parametrize("name", ["in_lava_red", "in_lava_flames"])
def test_the_view_from_inside_lava_is_read_as_lava(name):
    f = _frame(name)
    assert vision.lava_submerged(f) >= 0.75 > vision.LAVA_SUBMERGED_MIN
    assert vision.lava_fraction(f) < 0.02            # why the old reading missed it


@pytest.mark.parametrize("name", ["lake_from_the_bank", "nether_plateau", "burning_at_the_portal",
                                  "falling_over_the_sea"])
def test_lava_seen_from_outside_and_flames_are_not(name):
    assert vision.lava_submerged(_frame(name)) < 0.30 < vision.LAVA_SUBMERGED_MIN


def _reflex(name: str, state: dict) -> dict:
    out = subprocess.run([sys.executable, "-c", skills.STARTER_REFLEXES[name]],
                         input=json.dumps(state), capture_output=True, text=True, check=True)
    return json.loads(out.stdout) if out.stdout.strip() else {}


STATE = {"pos": {"x": -409.0, "y": 27.5, "z": -625.0}, "pos_prev": {"x": -409.0, "y": 27.6, "z": -625.0},
         "health": 6.0, "health_prev": 10.0, "lava_frac": 0.0, "fire_frac": 0.0, "gui_open": False,
         "dimension": "the Nether", "entry": "raw", "queue_len": 3,
         "hotbar": [{"slot": 3, "item": "cobblestone", "n": 20}]}


def test_the_shipped_reflexes_tell_lava_from_a_mob():
    """The recorded state: 4 health lost in four ticks, both fractions 0.000."""
    assert "a mob is at you" in _reflex("hit.py", STATE)["note"]          # as before, off lava
    assert _reflex("lava_ahead.py", STATE) == {}
    under = {**STATE, "in_lava": True}
    assert _reflex("hit.py", under) == {}                                  # not a mob
    out = _reflex("lava_ahead.py", under)
    assert out["stop"] and out["note"].startswith("IN LAVA") and out["actions"]


def test_go_to_sneak_walks_without_a_hop_and_stops_with_the_reason():
    from mcu_worldmodel.agent import WorldModelAgent

    assert "sneak" not in P.go_to(1.0, 9.0)[0]["_goto"]                    # the default is the old walk
    gt = P.go_to(1.0, 9.0, sneak=True)[0]["_goto"]
    assert gt["sneak"] is True
    notes: list[str] = []
    agent = SimpleNamespace(_cur_pos={"x": 1.0, "y": 64.0, "z": 2.0, "yaw": 0.0, "pitch": 0.0},
                            cursor_stats={}, step=10, _last_pov=None,
                            memory=SimpleNamespace(add_note=notes.append),
                            _keep_event_frame=lambda *a, **k: None,
                            grid=SimpleNamespace(mark_blocked=lambda *a: notes.append("MARKED")))
    agent._goto_stalled = lambda g, p, mk: WorldModelAgent._goto_stalled(agent, g, p, mk)
    act = WorldModelAgent._goto_tick(agent, gt, lambda **kw: kw)
    assert act["forward"] == 1 and act["sneak"] == 1 and "jump" not in act and "sprint" not in act
    for _ in range(3):                                                      # the edge: no progress
        act = WorldModelAgent._goto_tick(agent, gt, lambda **kw: kw)
    assert act is None and "MARKED" not in notes
    assert "with sneak stopped at" in notes[-1] and "a block edge with a drop" in notes[-1]


def test_a_continued_life_is_not_asked_for_the_earlier_lifes_milestones():
    from mcu_worldmodel.milestones import MilestoneLedger
    from task_milestones import load_given_milestones, load_given_settled, load_milestone_cfg

    t = "ender_dragon_resume"
    led = MilestoneLedger(load_milestone_cfg(t), task_name=t, given=load_given_milestones(t),
                          settled=load_given_settled(t))
    assert led.settled and len(led.given) == 15 and led.next_target()["identity"] == "netherrack"
    block = led.progress_block()
    assert block.count("[=]") == 15 and "bank it early" not in block
    assert "counted there" in led.progress_line()
    # the second-half starts keep theirs open: the scorer credits only what happens in the run
    t = "ender_dragon_portal"
    led = MilestoneLedger(load_milestone_cfg(t), task_name=t, given=load_given_milestones(t),
                          settled=load_given_settled(t))
    assert not led.settled and led.next_target()["identity"] == "mine_log"
    assert "bank it early" in led.progress_block()
