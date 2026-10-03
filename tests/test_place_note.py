"""place_at / use_at name a fallback face and an unsettled aim in their note (the stray
blocks of the recorded portal frames came from both); look_at keeps the heading for a
cell straight overhead."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np


def _agent(pos, inv, stats=None):
    notes: list[str] = []
    st = dict(stats or {})

    def stat_now(event, obj):
        return float(st.get(f"{event}.{obj}", 0.0))

    return SimpleNamespace(
        _gui_open=False, _cur_pos=dict(pos), _cur_inv=dict(inv), cursor_stats={}, step=100,
        stat_now=stat_now, memory=SimpleNamespace(add_note=notes.append), notes=notes,
        ledger=SimpleNamespace(_prev={}), _note_failure=lambda label: None,
        _flush_tail=lambda note, stat: notes.append(note))


def _mk(**kw):
    return {"camera": [0.0, 0.0], **kw}


def test_place_note_names_a_fallback_face_and_an_unsettled_aim():
    from mcu_worldmodel import macros_world as MW

    pos = {"x": 0.5, "y": 10.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    agent = _agent(pos, {"obsidian": 9}, {"use_item.obsidian": 1.0})
    st = MW.new_use_state((0, 10, 2), "obsidian", "below", "place", 1, "place_at(obsidian)")
    st.update(phase="verify", face="north", base_use=0.0, base_inv={"obsidian": 10}, gui0=False,
              pos0=(0.5, 10.0, 0.5), aim_off=7.5)
    assert MW._useat_tick(agent, st, _mk) is None
    note = agent.notes[-1]
    assert "placed at (0, 10, 2) (north face)" in note and "obsidian -1" in note
    assert "NOT the below face you named" in note and "clicked 7.5 degrees off" in note
    # the face asked for, a settled aim: nothing to doubt
    agent = _agent(pos, {"obsidian": 9}, {"use_item.obsidian": 1.0})
    st = MW.new_use_state((0, 10, 2), "obsidian", "below", "place", 1, "place_at(obsidian)")
    st.update(phase="verify", base_use=0.0, base_inv={"obsidian": 10}, gui0=False, pos0=(0.5, 10.0, 0.5))
    assert MW._useat_tick(agent, st, _mk) is None
    assert "NOT the" not in agent.notes[-1] and "degrees off" not in agent.notes[-1]
    # the aim phase records how far off the crosshair still was when the click came
    agent = _agent({"x": 0.5, "y": 10.0, "z": 0.5, "pitch": 0.0, "yaw": 180.0}, {"obsidian": 10},
                   {"use_item.obsidian": 0.0})
    st = MW.new_use_state((0, 10, 2), "obsidian", "below", "place", 1, "place_at(obsidian)")
    for _ in range(MW.AIM_TICKS + 8):
        MW.use_step(agent, st, _mk)
        if st["phase"] != "aim":
            break
    assert st["phase"] == "click" and st["aim_off"] and st["aim_off"] > 90.0


def test_look_at_keeps_the_heading_for_a_cell_straight_overhead():
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.testing import fake_info

    info = fake_info()
    info["location_stats"].update(xpos=np.array(0.5), ypos=np.array(10.0), zpos=np.array(0.5),
                                  pitch=np.array(0.0), yaw=np.array(90.0))
    acts, _ = P.look_at(info, x=0.55, y=13.5, z=0.6)       # 7 cm off the axis: no heading of its own
    assert abs(sum(a["camera"][1] for a in acts)) < 1e-6 and sum(a["camera"][0] for a in acts) < -60.0
    acts, _ = P.look_at(info, x=3.5, y=13.5, z=0.5)        # a real offset: the heading turns
    assert abs(sum(a["camera"][1] for a in acts)) > 10.0
