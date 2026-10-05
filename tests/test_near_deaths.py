"""`--near-deaths`: a death is named when the respawn is close to where it happened.

The shipped rule names a death by its teleport (15+ blocks, health full). A death at the
spawn -- a fight there, a fall onto it -- has no teleport, and on this engine no health
drop either: a staged fall (slurm/skill_reuse3.sbatch SMOKE=death) read health 20 on the
tick before and the tick after. What the respawn tick does show is three things at once:
the carried stacks gone, the camera at exactly 0/0, the death screen closed. Two of the
three name the death; one alone never does.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from test_pins_chassis import _pov, drive_chassis
from test_release_pins import _arm


def _tick(agent, step: int, *, inventory: dict, pitch: float, yaw: float, gui: bool = False,
          xyz=(7.0, 64.0, 2.0), health: float = 20.0) -> None:
    """One observed tick with the given numbers."""
    from mcu_worldmodel.testing import fake_info
    info = fake_info(inventory=inventory)
    info["location_stats"].update(xpos=np.array(xyz[0]), ypos=np.array(xyz[1]),
                                  zpos=np.array(xyz[2]), pitch=np.array(pitch),
                                  yaw=np.array(yaw))
    info["health"] = np.array(health)
    info["isGuiOpen"] = gui
    info["pov"] = _pov(step)
    agent.observe(info, step)


def _life(tmp: Path, arm: str = "mfm", **kw):
    agent, _ = drive_chassis(tmp, MODE[arm], steps=20, **kw, **_arm(arm))
    return agent


MODE = {"mfm": "mfm", "logbook": "logbook"}
KIT = {"diamond_sword": 1, "cobblestone": 32, "cooked_beef": 16}


def _notes(agent) -> str:
    """The notes waiting for the next log block plus what the log already holds."""
    return "\n".join(agent.memory._pending_notes) + (agent.memory.root / "logs.txt").read_text()


def _died(agent) -> bool:
    return "YOU DIED" in _notes(agent)


def test_the_respawn_at_the_death_point_is_named(tmp_path: Path):
    agent = _life(tmp_path, near_deaths=True)
    _tick(agent, 21, inventory=KIT, pitch=70.0, yaw=100.0)
    agent.queue.append(({"forward": 1}, 0))                 # a plan is still running
    _tick(agent, 22, inventory=KIT, pitch=70.0, yaw=100.0, gui=True)      # the death screen
    assert not _died(agent)
    _tick(agent, 23, inventory={}, pitch=0.0, yaw=0.0)                    # the respawn
    text = _notes(agent)
    assert "YOU DIED at (7, 64, 2) and respawned at (7, 64, 2), 0 block(s) from there." in text
    assert "dropped at the death point" in text and "pitch 0, yaw 0" in text
    assert not agent.queue                                   # the plan it voided is dropped
    assert agent.cursor_stats["deaths"] == 1 and agent.cursor_stats["near_deaths"] == 1
    assert agent.report()["near_deaths"] is True
    # named once: the ticks after it are an ordinary life
    _tick(agent, 24, inventory={}, pitch=0.0, yaw=0.0)
    _tick(agent, 25, inventory={"cobblestone": 32}, pitch=0.0, yaw=0.0)   # walked onto the pile
    assert agent.cursor_stats["deaths"] == 1


@pytest.mark.parametrize("before, screen, after, why", [
    # the stacks gone and the camera reset, the screen tick not seen
    (dict(inventory=KIT, pitch=70.0, yaw=100.0), None, dict(inventory={}, pitch=0.0, yaw=0.0),
     "wiped + pose"),
    # nothing carried: the camera reset as the death screen closes
    (dict(inventory={}, pitch=70.0, yaw=100.0), dict(inventory={}, pitch=70.0, yaw=100.0),
     dict(inventory={}, pitch=0.0, yaw=0.0), "pose + screen"),
    # killed again before turning (camera already at 0/0): the stacks gone as the screen closes
    (dict(inventory=KIT, pitch=0.0, yaw=0.0), dict(inventory=KIT, pitch=0.0, yaw=0.0),
     dict(inventory={}, pitch=0.0, yaw=0.0), "wiped + screen"),
])
def test_two_of_the_three_signs_name_it(tmp_path: Path, before, screen, after, why):
    agent = _life(tmp_path, near_deaths=True)
    _tick(agent, 21, **before)
    if screen:
        _tick(agent, 22, gui=True, **screen)
    _tick(agent, 23, **after)
    assert _died(agent), why


@pytest.mark.parametrize("before, screen, after, why", [
    # the last block placed empties the inventory
    (dict(inventory={"cobblestone": 1}, pitch=40.0, yaw=90.0), None,
     dict(inventory={}, pitch=40.0, yaw=90.0), "wiped alone"),
    # a look that ends on exactly 0/0
    (dict(inventory=KIT, pitch=6.0, yaw=-12.0), None, dict(inventory=KIT, pitch=0.0, yaw=0.0),
     "pose alone"),
    # a screen the plan closed
    (dict(inventory=KIT, pitch=40.0, yaw=90.0), dict(inventory=KIT, pitch=40.0, yaw=90.0),
     dict(inventory=KIT, pitch=40.0, yaw=90.0), "screen alone"),
    # standing at 0/0 the whole time is not a reset
    (dict(inventory={"cobblestone": 1}, pitch=0.0, yaw=0.0), None,
     dict(inventory={}, pitch=0.0, yaw=0.0), "no turn"),
])
def test_one_sign_alone_is_not_a_death(tmp_path: Path, before, screen, after, why):
    agent = _life(tmp_path, near_deaths=True)
    _tick(agent, 21, **before)
    if screen:
        _tick(agent, 22, gui=True, **screen)
    _tick(agent, 23, **after)
    assert not _died(agent), why
    assert "deaths" not in agent.cursor_stats


def test_health_must_be_full_as_it_is_after_a_respawn(tmp_path: Path):
    agent = _life(tmp_path, near_deaths=True)
    _tick(agent, 21, inventory=KIT, pitch=70.0, yaw=100.0, health=9.0)
    _tick(agent, 22, inventory={}, pitch=0.0, yaw=0.0, health=9.0)
    assert not _died(agent)


def test_without_the_flag_the_same_ticks_pass_unnamed(tmp_path: Path):
    agent = _life(tmp_path)
    _tick(agent, 21, inventory=KIT, pitch=70.0, yaw=100.0)
    agent.queue.append(({"forward": 1}, 0))
    _tick(agent, 22, inventory=KIT, pitch=70.0, yaw=100.0, gui=True)
    _tick(agent, 23, inventory={}, pitch=0.0, yaw=0.0)
    assert not _died(agent) and agent.queue
    assert "near_deaths" not in agent.report()


def test_the_far_death_is_named_as_it_always_was(tmp_path: Path):
    """The shipped rule and its sentence are untouched, flag on or off."""
    texts = []
    for name, kw in (("off", {}), ("on", {"near_deaths": True})):
        agent = _life(tmp_path / name, **kw)
        # (the move out to the mine is itself a teleport for this fixture: counted, not read)
        _tick(agent, 21, inventory=KIT, pitch=70.0, yaw=100.0, xyz=(300.0, 12.0, -40.0))
        before = agent.cursor_stats.get("deaths", 0)
        _tick(agent, 22, inventory={}, pitch=0.0, yaw=0.0, xyz=(7.0, 64.0, 2.0))
        note = [n for n in agent.memory._pending_notes if "YOU DIED" in n][-1]
        assert "YOU DIED at (300, 12, -40) and respawned at (7, 64, 2)." in note
        assert "stair_down beside the site" in note and "block(s) from there" not in note
        assert agent.cursor_stats["deaths"] == before + 1
        assert "near_deaths" not in agent.cursor_stats
        texts.append(note)
    assert texts[0] == texts[1]


def test_it_is_the_chassis_not_the_memory(tmp_path: Path):
    """Any arm can be run with it: a logbook life names the same death."""
    agent = _life(tmp_path, arm="logbook", near_deaths=True)
    _tick(agent, 21, inventory=KIT, pitch=70.0, yaw=100.0)
    _tick(agent, 22, inventory=KIT, pitch=70.0, yaw=100.0, gui=True)
    _tick(agent, 23, inventory={}, pitch=0.0, yaw=0.0)
    assert _died(agent)
