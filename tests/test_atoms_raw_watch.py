"""`--atoms`: the wall watcher samples raw attack holds, exactly as it samples a macro.

g4_mfm_gpt6_diamond v1-v3 (2026-09-11) mined 12,000 steps each on raw {"attack": 1}
holds -- the only mining step an atoms arm has that is cut at the break -- and the
watcher, which lived only in the withheld macros and mine_ahead, never sampled them.
"""
from pathlib import Path

import pytest

HOLDS = [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 30}] * 4},
          "message": f"[PLAN]\nholds {i}"} for i in range(30)]
WALKS = [{"actions": {"actions": [{"action": {"forward": 1}, "repeat": 20},
                                  {"action": {"camera": [5, 0]}, "repeat": 1}] * 4},
          "message": f"[PLAN]\nwalk {i}"} for i in range(30)]


@pytest.fixture
def cyan_everywhere(monkeypatch):
    from mcu_worldmodel import vision
    monkeypatch.setattr(vision, "find_ore", lambda frame: ("diamond", (320, 180, 40)))


def test_atoms_raw_holds_are_watched(tmp_path: Path, cyan_everywhere):
    from test_pins_chassis import drive_chassis
    agent, _ = drive_chassis(tmp_path, "mfm", steps=140, script=HOLDS,
                             thin=True, own=True, atoms=True)
    log = (agent.memory.root / "logs.txt").read_text()
    assert agent.cursor_stats.get("raw_hold_flags", 0) >= 1
    assert "mining stopped: diamond-ore-like speckles" in log
    assert '{"attack": 1} holds (repeat 30' in log and "aim_at_ore" not in log
    # one flag per 100 steps, like a macro: 140 steps of holds is at most two
    assert agent.cursor_stats["raw_hold_flags"] <= 2
    assert agent.cursor_stats["raw_hold_flags"] == agent.cursor_stats.get("ore_flagged")


def test_baseline_raw_holds_stay_unwatched(tmp_path: Path, cyan_everywhere):
    from test_pins_chassis import drive_chassis
    agent, _ = drive_chassis(tmp_path, "logbook", steps=140, script=HOLDS + WALKS)  # walks are unwatched on this harness too
    log = (agent.memory.root / "logs.txt").read_text()
    assert "raw_hold_flags" not in agent.cursor_stats
    assert "mining stopped" not in log and not agent.cursor_stats.get("ore_flagged")


def test_cut_short_hint_under_atoms_names_holds():
    from mcu_worldmodel.agent import _cut_short_hint
    assert '{"attack": 1} hold' in _cut_short_hint(True) and "mine_ahead" in _cut_short_hint(True)
    assert "mine_forward/strip_mine/stair_down" in _cut_short_hint(False)
