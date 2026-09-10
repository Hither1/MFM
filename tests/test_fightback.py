"""The fightback after an abandoned bunker (agent._weapon_slot / _arm_fightback /
_fightback_tick / _in_hole / _in_shaft). og8_mfm, 2026-09-07: at the bottom of its own
shaft a zombie fell into the cell; the bunker dug two blocks with it aboard and capped
them both in -- 4.5 hp every 20 ticks, dead at step 2603 with a diamond sword in the
inventory and the kit lost."""
from __future__ import annotations

from types import SimpleNamespace


def _ns(info=None, pos=None, **kw):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    ns = SimpleNamespace(
        SWORDS=A.SWORDS, AXES=A.AXES, PICKAXES=A.PICKAXES, WEAPON_PERIOD=A.WEAPON_PERIOD,
        PILLAR_BLOCKS=A.PILLAR_BLOCKS,
        FIGHTBACK_TICKS=A.FIGHTBACK_TICKS, FIGHTBACK_SWEEP=A.FIGHTBACK_SWEEP,
        CRITICAL_HP=A.CRITICAL_HP, BUNKER_HOLE_STEPS=A.BUNKER_HOLE_STEPS,
        _cur_info=info, _cur_pos=dict(pos or {}), _gui_open=False, _last_health=15.0,
        _close_armed=False, _last_bunker=None, cursor_stats={}, notes=notes,
        memory=SimpleNamespace(add_note=notes.append), stat_now=lambda a, b: 0.0,
        grid=SimpleNamespace(walked={}))
    ns._sword_slot = lambda info: A._sword_slot(ns, info)
    ns._weapon_slot = lambda info: A._weapon_slot(ns, info)
    ns._finish_fightback = lambda rf, why: A._finish_fightback(ns, rf, why)
    ns._guard_close = lambda action, mk: action
    ns._reflex = None
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_weapon_slot_prefers_sword_then_axe_then_pickaxe():
    from mcu_worldmodel.selftest import fake_info

    ns = _ns()
    assert ns._weapon_slot(fake_info(inventory={"iron_pickaxe": 1})) [1:] == ("iron_pickaxe", 17)
    w = ns._weapon_slot(fake_info(inventory={"iron_pickaxe": 1, "stone_axe": 1}))
    assert w[1:] == ("stone_axe", 20)
    w = ns._weapon_slot(fake_info(inventory={"iron_pickaxe": 1, "stone_axe": 1,
                                             "diamond_sword": 1}))
    assert w[1:] == ("diamond_sword", 9) and 1 <= w[0] <= 9
    assert ns._weapon_slot(fake_info(inventory={"cobblestone": 4})) is None


def test_fightback_sweeps_on_empty_swings_and_keeps_going_when_desperate():
    from mcu_worldmodel.agent import WorldModelAgent as A

    pos = {"x": 0.5, "y": 9.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    ns = _ns(pos=pos)
    rf = A._arm_fightback(ns, pos, 15.0, 0.0, (1, "diamond_sword", 9), desperate=True)
    ns._reflex = rf
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    a = A._fightback_tick(ns, rf, mk)
    assert a.get("hotbar_1") == 1 and rf["phase"] == "turn"
    acts = [A._fightback_tick(ns, rf, mk) for _ in range(16)]
    assert rf["phase"] == "turn" and rf["yaw"] == 45.0 and rf["sweeps"] == 1
    assert ns.cursor_stats["fightback_sweeps"] == 1
    # the sword's cadence: a swing on t = 1, 10 (period 9), never on the ticks between
    assert acts[0].get("attack") == 1 and acts[9].get("attack") == 1
    assert not any(acts[i].get("attack") for i in (1, 2, 5, 8, 11))
    # a critical health does not stop a desperate fight; it stops an ordinary one
    ns._last_health = 3.0
    ns._cur_pos.update({"yaw": 90.0})
    assert A._fightback_tick(ns, rf, mk) is not None
    rf2 = A._arm_fightback(ns, pos, 15.0, 90.0, (1, "diamond_sword"))
    A._fightback_tick(ns, rf2, mk)
    A._fightback_tick(ns, rf2, mk)
    assert A._fightback_tick(ns, rf2, mk) is None
    assert any("health critical" in n for n in ns.notes)


def test_fightback_closes_the_screen_first_when_asked():
    from mcu_worldmodel.agent import WorldModelAgent as A

    pos = {"x": 0.5, "y": 9.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    ns = _ns(pos=pos, _gui_open=True)
    rf = A._arm_fightback(ns, pos, 7.0, 0.0, (2, "iron_pickaxe", 17), desperate=True,
                          close_gui=True)
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    assert rf["phase"] == "close" and rf["period"] == 17
    a = A._fightback_tick(ns, rf, mk)
    assert a.get("inventory") == 1 and ns._close_armed
    ns._gui_open = False
    a = A._fightback_tick(ns, rf, mk)
    assert a.get("hotbar_2") == 1 and rf["phase"] == "turn"


def test_fightback_aims_at_the_cell_centre():
    from mcu_worldmodel.agent import WorldModelAgent as A

    ns = _ns()
    # pushed to the west wall of cell (0, 9, 0): the mob is toward +x -> yaw -90
    pos = {"x": 0.25, "y": 9.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    rf = A._arm_fightback(ns, pos, 15.0, 180.0, (1, "diamond_sword", 9), toward_center=True)
    assert abs(rf["yaw"] - (-90.0)) < 0.5
    # pushed to the north wall (z low): the mob is toward +z -> yaw 0
    pos = {"x": -3008.5, "y": 9.0, "z": -5568.9, "pitch": 0.0, "yaw": 140.0}
    rf = A._arm_fightback(ns, pos, 15.0, 140.0, (1, "diamond_sword", 9), toward_center=True)
    assert abs(rf["yaw"]) < 0.5
    # at the centre nothing is known: the given yaw stands
    pos = {"x": 0.5, "y": 9.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    rf = A._arm_fightback(ns, pos, 15.0, 33.0, (1, "diamond_sword", 9), toward_center=True)
    assert rf["yaw"] == 33.0
    # ... and the first empty sweep re-aims from where the push has left the avatar:
    # the corner (-.7, -.7) of the cell (stage s20) -> the mob is diagonal, yaw -45
    ns._cur_pos = {"x": -2999.7, "y": 16.0, "z": -5559.7, "pitch": 0.0, "yaw": 33.0}
    ns._reflex = rf
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    A._fightback_tick(ns, rf, mk)                        # equip
    for _ in range(17):                                  # turn (already at 33) + 16 swings
        a = A._fightback_tick(ns, rf, mk)
    assert rf["sweeps"] == 1 and abs(rf["yaw"] - (-45.0)) < 0.5 and rf["phase"] == "turn"
    assert not a.get("forward")                          # no step into the wall in a cell


def test_bunker_hands_over_when_its_swings_hit_the_mob():
    from mcu_worldmodel.agent import WorldModelAgent as A
    from mcu_worldmodel.selftest import fake_info

    info = fake_info(inventory={"iron_pickaxe": 1, "cobblestone": 8})
    pos = {"x": -2999.3, "y": 16.0, "z": -5559.7, "pitch": 90.0, "yaw": 0.0}
    dealt = {"v": 0.0}
    ns = _ns(info=info, pos=pos, step=2540, _last_health=15.5,
             stat_now=lambda a, b: dealt["v"])
    ns.grid.walked = {(-3000, 17, -5560): {}, (-3000, 16, -5560): {}}
    ns._pillar_slot = lambda info, min_qty=2: A._pillar_slot(ns, info, min_qty)
    ns._bunker_plan = lambda info: A._bunker_plan(ns, info)
    ns._finish_bunker = lambda rf, why: A._finish_bunker(ns, rf, why)
    ns._arm_fightback = lambda *a, **k: A._arm_fightback(ns, *a, **k)
    ns._fightback_tick = lambda rf, mk: A._fightback_tick(ns, rf, mk)
    ns._in_shaft = lambda cell: A._in_shaft(ns, cell)
    ns.PICKAXES = A.PICKAXES
    plan = ns._bunker_plan(info)
    assert plan is not None and plan[1] == "iron_pickaxe"
    rf = A._arm_bunker(ns, plan, pos)
    ns._reflex = rf
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    A._bunker_tick(ns, rf, mk)                       # equip the pickaxe
    a = A._bunker_tick(ns, rf, mk)                   # looking down already: the dig
    assert a.get("attack") == 1 and rf["phase"] == "dig"
    dealt["v"] = 39.0                                # the swing hit the zombie
    a = A._bunker_tick(ns, rf, mk)
    assert ns._reflex is not None and ns._reflex["kind"] == "fightback"
    assert ns._reflex["desperate"] and ns._reflex["item"] == "iron_pickaxe"
    assert ns.cursor_stats["bunker_intercepted"] == 1
    assert any("the swings hit the mob, not the floor" in n for n in ns.notes)
    assert any("FIGHTING BACK with the iron_pickaxe" in n and "nowhere to run" in n
               for n in ns.notes)


def test_in_hole_and_in_shaft():
    from mcu_worldmodel.agent import WorldModelAgent as A

    ns = _ns(_last_bunker={"step": 2560, "cell": (-3009, 11, -5569)})
    inside = {"x": -3008.3, "y": 9.0, "z": -5568.7, "pitch": 0.0, "yaw": 0.0}
    assert A._in_hole(ns, inside, 2583)
    assert not A._in_hole(ns, inside, 2560 + 601)                 # too long ago
    assert not A._in_hole(ns, {**inside, "y": 11.0}, 2583)        # back on the floor
    assert not A._in_hole(ns, {**inside, "x": -3007.5}, 2583)     # another column
    ns._last_bunker = None
    assert not A._in_hole(ns, inside, 2583)
    ns.grid.walked = {(-3009, 12, -5569): {}, (-3009, 11, -5569): {}}
    assert A._in_shaft(ns, (-3009, 11, -5569))
    assert not A._in_shaft(ns, (-3009, 12, -5569))
    assert not A._in_shaft(ns, (-3008, 11, -5569))
