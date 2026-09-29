"""The torch phase of the level tunnelling tick (agent._torch_due / _torch_step): every
TORCH_EVERY blocks underground, with a torch in the hotbar, the tunnel pauses, plants a
torch on the floor of the cell just left, takes the tool back and faces the heading
again. The 2026-09-06 runs carried torches through eleven DARK stretches and planted
none."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np


def _stub(info, pos):
    notes: list[str] = []
    st: dict[str, float] = {}

    def stat_now(event, obj):
        return float(st.get(f"{event}.{obj}", 0.0))

    from mcu_worldmodel.agent import WorldModelAgent as A

    return SimpleNamespace(
        TORCH_EVERY=A.TORCH_EVERY, TORCH_MAX_Y=A.TORCH_MAX_Y,
        _cur_info=info, _cur_pos=dict(pos), _cur_inv={"torch": 8, "diamond_pickaxe": 1},
        _gui_open=False, cursor_stats={}, stat_now=stat_now, stats=st,
        ledger=SimpleNamespace(_prev={}), memory=SimpleNamespace(add_note=notes.append),
        notes=notes)


def _mf(advanced: float) -> dict:
    return {"budget": 300, "ore": False, "p_lo": 35.0, "p_hi": 8.0, "jump": True,
            "down_by": None, "label": "strip_mine", "phase": "adv", "phase_t": 0,
            "base_breaks": 0.0, "start": (0.5, 64.0, 0.5), "adv_from": None,
            "broken": 10, "advanced": advanced, "stall": 0, "used": 200}


def test_torch_phase_plants_behind_and_restores_the_tool():
    from mcu_worldmodel import gui
    from mcu_worldmodel import macros_world as MW
    from mcu_worldmodel.agent import WorldModelAgent as A
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"torch": 8, "diamond_pickaxe": 1})
    info["equipped_items"] = {"mainhand": {"type": "diamond_pickaxe", "damage": np.array(0)}}
    torch_slot = gui.find_slots(info, "torch")[0][0]
    pick_slot = gui.find_slots(info, "diamond_pickaxe")[0][0]
    pos = {"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    ag = _stub(info, pos)
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}

    # Not due yet; due at TORCH_EVERY; never on the surface.
    mf = _mf(A.TORCH_EVERY - 1)
    assert not A._torch_due(ag, mf, pos) and mf["phase"] == "adv"
    assert not A._torch_due(ag, _mf(20.0), {**pos, "y": 60.0})
    mf = _mf(A.TORCH_EVERY)
    assert A._torch_due(ag, mf, pos) and mf["phase"] == "torch"
    target = tuple(mf["torch"]["use"]["target"])
    assert target == (0, 12, -1), target          # the cell behind, facing yaw 0 (+z)
    assert mf["torch"]["slot"] == torch_slot and mf["torch"]["back"] == pick_slot

    # select -> aim (camera) -> click -> done -> tool back -> face the heading.
    a = A._torch_step(ag, mf, mk)
    assert a.get(f"hotbar_{torch_slot + 1}") == 1
    a = A._torch_step(ag, mf, mk)
    assert a.get("camera") != [0.0, 0.0] and "use" not in a
    pitch, yaw, dist = MW.angles_to(pos, MW.aim_point(target, "below", 0.5))
    assert dist < MW.REACH
    ag._cur_pos.update({"pitch": pitch, "yaw": yaw})
    seen_use = False
    for _ in range(8):
        a = A._torch_step(ag, mf, mk)
        seen_use = seen_use or a.get("use") == 1
        if mf["torch"]["step"] != "place":
            break
    assert seen_use
    ag.stats["use_item.torch"] = 1.0
    while mf["torch"]["step"] == "place":
        A._torch_step(ag, mf, mk)
    assert mf["torches"] == 1 and ag.cursor_stats["torches_placed"] == 1
    a = A._torch_step(ag, mf, mk)
    assert a.get(f"hotbar_{pick_slot + 1}") == 1
    a = A._torch_step(ag, mf, mk)
    assert a["camera"][1] != 0.0                  # turning back toward yaw 0
    ag._cur_pos["yaw"] = 0.0
    assert A._torch_step(ag, mf, mk) is None
    # The next TORCH_EVERY blocks arm it again; less does not.
    mf["phase"] = "adv"
    assert not A._torch_due(ag, mf, pos)
    mf["advanced"] += A.TORCH_EVERY
    assert A._torch_due(ag, mf, pos)


def test_no_torch_no_phase():
    from mcu_worldmodel.agent import WorldModelAgent as A
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"diamond_pickaxe": 1})
    pos = {"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    ag = _stub(info, pos)
    mf = _mf(30.0)
    assert not A._torch_due(ag, mf, pos) and mf["phase"] == "adv"
