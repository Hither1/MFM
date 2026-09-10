"""Falls: mid-air ticks are not walked cells (grid.observe, FALL_DY) and an unplanned drop
of 4+ blocks stops the plan on landing (agent._fall_guard). og13_mfm 2026-09-07 18768:
a go_to fell 13 blocks in the Nether, the stall branch queued pillar_up(2) toward a
mid-air cell, the model jumped on and fell 9 more, dead with the kit."""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from mcu_worldmodel.grid import Grid


def _pos(x, y, z, pitch=0.0, yaw=0.0):
    return {"x": float(x), "y": float(y), "z": float(z), "pitch": float(pitch),
            "yaw": float(yaw)}


def _free_fall(y0, y1):
    """Feet heights of a free fall from y0 to the floor y1 (0.08 blocks/tick^2)."""
    ys, y, v = [], y0, 0.0
    while y > y1:
        v += 0.08
        y = max(y1, y - v)
        ys.append(y)
    return ys


def test_mid_air_cells_are_not_walked():
    g = Grid()
    step = 0
    for x in range(0, 3):                                 # a walk at y 50
        g.observe(step, _pos(x + 0.5, 50, 0.5)); step += 4
    for y in _free_fall(50.0, 37.0) + [37.0, 37.0]:       # the hole: 13 blocks
        g.observe(step, _pos(2.5, y, 1.5)); step += 1
    levels = sorted(c[1] for c in g.walked if c[0] == 2 and c[2] == 1)
    assert 37 in levels and 50 not in levels              # the landing is on the map
    assert all(lv <= 49 for lv in levels if lv != 37) and min(lv for lv in levels if lv != 37) >= 48
    assert g.above(_pos(2.5, 37, 1.5)) is None            # no fake rim 2-8 blocks up
    assert (2, 37, 1) not in g.edges or all(abs(n[1] - 37) <= 2 for n in g.edges[(2, 37, 1)])
    # a staircase down and a jump down one block still record every step
    s = Grid(); step = 0
    for i in range(6):
        for y in (60 - i, 60 - i - 0.2, 60 - i - 0.45, 60 - i - 0.75, 60 - i - 1.0, 60 - i - 1.0):
            s.observe(step, _pos(i + 0.5, y, 0.5)); step += 1
    assert {c[1] for c in s.walked} >= {60, 59, 58, 57, 56, 55, 54}


def _ns(queue, dimension="the Overworld"):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    return SimpleNamespace(_fall=None, queue=queue, _reflex=None, cursor_stats={}, notes=notes,
                           _gui_open=False, _dimension=dimension,
                           memory=SimpleNamespace(add_note=notes.append),
                           FALL_MIN_DROP=A.FALL_MIN_DROP, FALL_VMAX=A.FALL_VMAX)


def _run(ns, ys, x=-383.0, z=-686.65, step0=18740):
    from mcu_worldmodel.agent import WorldModelAgent as A

    for i, y in enumerate(ys):
        A._fall_guard(ns, step0 + i, _pos(x, y, z))


def test_fall_guard_stops_the_plan_on_landing():
    ns = _ns([({"_goto": {}}, 1), ({"forward": 1}, 1)], dimension="the Nether")
    _run(ns, [50.0, 50.0, 50.0] + _free_fall(50.0, 37.0) + [37.0, 37.0, 37.0, 37.0])
    assert ns.cursor_stats.get("fall_stops") == 1 and ns.queue == []
    assert len(ns.notes) == 1 and ns.notes[0].startswith("FELL 13 blocks to (-383, 37, -687)")
    assert "2 action(s)" in ns.notes[0] and "In the Nether every ledge ends in lava" in ns.notes[0]
    # standing on, nothing more fires; a later 2-block hop does not either
    ns.queue = [({"forward": 1}, 1)]
    _run(ns, [37.0] * 5 + _free_fall(37.0, 35.0) + [35.0] * 4, step0=18800)
    assert ns.cursor_stats["fall_stops"] == 1 and ns.queue


def test_fall_guard_ignores_walked_descents_and_swims():
    from mcu_worldmodel.agent import WorldModelAgent as A

    ns = _ns([({"forward": 1}, 1)])
    ys = []
    for i in range(8):                                    # a staircase: one block per 6 ticks
        ys += [60 - i, 60 - i - 0.2, 60 - i - 0.45, 60 - i - 0.75, 60 - i - 1.0, 60 - i - 1.0]
    _run(ns, ys)
    assert not ns.cursor_stats.get("fall_stops") and ns.queue
    ns = _ns([({"forward": 1}, 1)])
    _run(ns, [40 - 0.1 * i for i in range(80)] + [32.0] * 3)   # a swim down 8 blocks
    assert not ns.cursor_stats.get("fall_stops") and ns.queue
    # a jump up one block and down again
    ns = _ns([({"forward": 1, "jump": 1}, 1)])
    _run(ns, [50, 50.42, 50.75, 50.98, 51.1, 51.0, 50.8, 50.5, 50.1, 50.0, 50.0, 50.0])
    assert not ns.cursor_stats.get("fall_stops")
    # nothing queued and no reflex: nothing to stop, no note
    ns = _ns([])
    _run(ns, [50.0, 50.0] + _free_fall(50.0, 40.0) + [40.0] * 3)
    assert not ns.cursor_stats.get("fall_stops") and not ns.notes
    assert A.FALL_MIN_DROP == 4.0
