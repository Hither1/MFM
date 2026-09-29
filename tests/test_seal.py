"""The flee-then-seal reflex (agent._arm_seal / _seal_tick): after the sprint the
runner turns to face the way back, clicks the floor's top so a block fills the cell at
feet level, clicks that block's top so one fills the head cell, and reports. Measured
2026-09-06: the blind fightback dealt 0 damage in 3 reflexes, the bunker was hit into
4 times of 4, the fight macro in a dark tunnel traded 1 swing for 15 hp."""
from __future__ import annotations

from types import SimpleNamespace



def _stub(info, pos, inv):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    ns = SimpleNamespace(
        SEAL_TICKS=A.SEAL_TICKS, FLEE_TICKS=A.FLEE_TICKS, PILLAR_BLOCKS=A.PILLAR_BLOCKS,
        _cur_info=info, _cur_pos=dict(pos), _cur_inv=dict(inv), cursor_stats={},
        memory=SimpleNamespace(add_note=notes.append), notes=notes)
    ns._pillar_slot = lambda info, min_qty=2: A._pillar_slot(ns, info, min_qty)
    ns._finish_seal = lambda rf, placed, why: A._finish_seal(ns, rf, placed, why)
    ns._reflex = None
    return ns


def test_seal_walls_the_way_back():
    from mcu_worldmodel import gui
    from mcu_worldmodel.agent import WorldModelAgent as A
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"cobblestone": 16, "diamond_pickaxe": 1})
    slot = gui.find_slots(info, "cobblestone")[0][0] + 1
    # Ran 6 blocks toward +z (yaw 0) from z 0.5; the attacker is behind, toward -z.
    pos = {"x": 0.5, "y": 12.0, "z": 6.5, "pitch": 0.0, "yaw": 0.0}
    ag = _stub(info, pos, {"cobblestone": 16})
    rf = {"kind": "flee", "phase": "run", "yaw": 0.0, "t": 61, "remaining": 100,
          "x0": 0.5, "z0": 0.5, "mark": (0.5, 6.0), "seal": True}
    assert A._arm_seal(ag, rf)
    assert rf["feet"] == (0, 12, 5) and rf["head"] == (0, 13, 5) and rf["slot"] == slot
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    a = A._seal_tick(ag, rf, mk)
    assert a.get(f"hotbar_{slot}") == 1
    # Turning: the yaw swings toward 180 (facing -z) and the pitch goes down.
    a = A._seal_tick(ag, rf, mk)
    assert abs(a["camera"][1]) == 30.0 and "use" not in a
    from mcu_worldmodel import macros_world as MW
    pitch, yaw, _ = MW.angles_to(pos, MW.aim_point((0, 12, 5), "below", 0.5))
    ag._cur_pos.update({"pitch": pitch, "yaw": yaw})
    a = A._seal_tick(ag, rf, mk)
    assert a.get("use") == 1 and rf["phase"] == "seal_wait_feet"
    ag._cur_inv["cobblestone"] = 15                    # the feet block went down
    a = A._seal_tick(ag, rf, mk)
    assert rf["phase"] == "seal_head"
    pitch, yaw, _ = MW.angles_to(ag._cur_pos, MW.aim_point((0, 13, 5), "below", 0.5))
    ag._cur_pos.update({"pitch": pitch, "yaw": yaw})
    a = A._seal_tick(ag, rf, mk)
    assert a.get("use") == 1
    ag._cur_inv["cobblestone"] = 14
    assert A._seal_tick(ag, rf, mk) is None
    assert any("WALLED the passage behind you with two cobblestone at (0, 12, 5)" in n
               for n in ag.notes)
    assert ag.cursor_stats["seal_blocks"] == 2


def test_seal_needs_a_block_and_a_run():
    from mcu_worldmodel.agent import WorldModelAgent as A
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"diamond_pickaxe": 1})
    pos = {"x": 0.5, "y": 12.0, "z": 6.5, "pitch": 0.0, "yaw": 0.0}
    ag = _stub(info, pos, {})
    rf = {"kind": "flee", "phase": "run", "yaw": 0.0, "t": 61, "remaining": 100,
          "x0": 0.5, "z0": 0.5, "mark": (0.5, 6.0), "seal": True}
    assert not A._arm_seal(ag, rf)                    # nothing to place
    info = fake_info(inventory={"cobblestone": 16})
    ag = _stub(info, {**pos, "z": 1.5}, {"cobblestone": 16})
    rf["x0"], rf["z0"] = 0.5, 0.5
    assert not A._arm_seal(ag, rf)                    # ran only one block
