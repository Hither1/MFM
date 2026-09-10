"""The shaft guard: grid.drop_ahead (a walked column of consecutive levels, last walked
downward) and agent._shaft_guard (drop the plan before the feet enter it).
og9_mfm 2026-09-07 step 19286: mine_forward from a stair at y 67 broke into its own
y 9..67 shaft one block away and the avatar fell 58 blocks; the column was on the map."""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from mcu_worldmodel.grid import Grid


def _pos(x, y, z, pitch=0.0, yaw=0.0):
    return {"x": float(x), "y": float(y), "z": float(z), "pitch": float(pitch),
            "yaw": float(yaw)}


def _dig(g: Grid, x, z, top, bottom, step=1000, per=5):
    for y in range(top, bottom - 1, -1):
        g.observe(step, _pos(x + 0.5, y, z + 0.5))
        step += per
    return step


def test_drop_ahead_flags_a_dug_column_only():
    g = Grid()
    end = _dig(g, -3005, -5581, 67, 9)                    # og9's shaft
    d = g.drop_ahead((-3005, 67, -5581))
    assert d == {"top": 67, "bottom": 9, "drop": 58, "dug": 1000, "reached": end - 5}
    assert g.drop_ahead((-3005, 66, -5581))["drop"] == 57  # entering mid-column
    assert g.drop_ahead((-3005, 68, -5581))["drop"] == 59  # one above the mouth: the floor is open
    assert g.drop_ahead((-3005, 69, -5581)) is None        # two above: solid ground could be there
    assert g.drop_ahead((-3005, 9, -5581)) is None         # the bottom itself
    assert g.drop_ahead((-3005, 12, -5581)) is None        # a 3-block drop is no shaft
    assert g.drop_ahead((-3005, 13, -5581))["drop"] == 4
    assert g.drop_ahead((-3004, 67, -5581)) is None        # the next column
    # a pillar: the same levels walked bottom first
    p = Grid()
    step = 0
    for y in range(60, 70):
        p.observe(step, _pos(0.5, y, 0.5)); step += 5
    assert p.drop_ahead((0, 69, 0)) is None
    # a staircase: one level per column
    s = Grid()
    step = 0
    for i in range(10):
        s.observe(step, _pos(0.5 + i, 70 - i, 0.5)); step += 5
    assert all(s.drop_ahead((i, 70 - i, 0)) is None for i in range(10))
    # a fall records no intermediate levels: not a shaft (nothing to go on)
    f = Grid()
    f.observe(1, _pos(0.5, 70, 0.5)); f.observe(2, _pos(0.5, 50, 0.5))
    assert f.drop_ahead((0, 70, 0)) is None
    # the shaft pillared back out of is solid again
    step = end
    for y in range(9, 68):
        g.observe(step, _pos(-3004.5, y, -5580.5)); step += 5
    assert g.drop_ahead((-3005, 67, -5581)) is None
    # and dug once more, open again; the index follows the walked set
    _dig(g, -3005, -5581, 67, 9, step=step)
    assert g.drop_ahead((-3005, 67, -5581))["drop"] == 58


def _ns(g: Grid, queue):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    ns = SimpleNamespace(grid=g, _gui_open=False, _pos_hist=deque(maxlen=5), queue=queue,
                         _reflex=None, cursor_stats={}, action_num=5, notes=notes,
                         memory=SimpleNamespace(add_note=notes.append),
                         _last_shaft=(None, -1), SHAFT_LOOKAHEAD=A.SHAFT_LOOKAHEAD,
                         SHAFT_LOOKAHEAD_MAX=A.SHAFT_LOOKAHEAD_MAX)
    ns._queue_head_action = lambda: A._queue_head_action(ns)
    return ns


def _walk(ns, poses, step0=100):
    from mcu_worldmodel.agent import WorldModelAgent as A

    for i, pos in enumerate(poses):
        ns._pos_hist.append((step0 + i, pos["x"], pos["y"], pos["z"]))
        A._shaft_guard(ns, step0 + i, pos)


def test_shaft_guard_stops_the_walk_before_the_column():
    g = Grid()
    _dig(g, -3005, -5581, 67, 9)
    # og9's geometry: at y 67 walking north (yaw 180) toward z -5580, the shaft at z -5581
    ns = _ns(g, [({"_goto": {}, "forward": 0}, 1)] * 3)
    _walk(ns, [_pos(-3004.6, 67, z, yaw=180) for z in (-5578.6, -5578.8, -5579.0, -5579.2, -5579.4)])
    assert ns.queue == [] and ns.cursor_stats["shaft_stops"] == 1
    assert len(ns.notes) == 1 and "SHAFT AHEAD" in ns.notes[0]
    assert "(-3005, 67, -5581)" in ns.notes[0] and "falls 58 blocks (55 hp, FATAL)" in ns.notes[0]
    assert "steps 1000-1290" in ns.notes[0] and "3 action(s)" in ns.notes[0]
    assert g.hazard[(-3005, 67, -5581)]["kind"].startswith("your open shaft")
    # the same column within the same action fires once (any level); a new action afresh
    ns.queue = [({"forward": 1}, 1)]
    _walk(ns, [_pos(-3004.6, 68, -5579.5, yaw=180)], step0=200)
    assert ns.cursor_stats["shaft_stops"] == 1 and ns.queue
    ns.action_num = 8
    _walk(ns, [_pos(-3004.6, 67, -5579.5, yaw=180)], step0=300)
    assert ns.cursor_stats["shaft_stops"] == 2 and ns.queue == []


def test_shaft_guard_facing_sneak_and_the_bottom():
    g = Grid()
    _dig(g, -3005, -5581, 67, 9)
    # standing still against the wall with `forward` queued (mine_forward): the facing counts
    ns = _ns(g, [({"forward": 1, "attack": 1}, 1)] * 2)
    _walk(ns, [_pos(-3004.6, 67, -5579.7, yaw=180)] * 2)
    assert ns.cursor_stats.get("shaft_stops") == 1 and ns.queue == []
    # facing the other way with `back` queued
    ns = _ns(g, [({"back": 1}, 1)])
    _walk(ns, [_pos(-3004.6, 67, -5579.7, yaw=0)] * 2)
    assert ns.cursor_stats.get("shaft_stops") == 1
    # sneaking is NOT exempt: in the simulator sneak + forward walked off the edge (s23)
    ns = _ns(g, [({"forward": 1, "sneak": 1}, 1)])
    _walk(ns, [_pos(-3004.6, 67, z, yaw=180) for z in (-5579.2, -5579.4, -5579.6)])
    assert ns.cursor_stats.get("shaft_stops") == 1 and ns.queue == []
    # nothing queued and no moving reflex: momentum alone, nothing to stop
    ns = _ns(g, [])
    _walk(ns, [_pos(-3004.6, 67, z, yaw=180) for z in (-5579.2, -5579.4, -5579.6)])
    assert not ns.cursor_stats.get("shaft_stops") and not ns.notes
    # a teleport (a death, a portal) is not a walk toward anything
    ns = _ns(g, [({"forward": 1}, 1)])
    _walk(ns, [_pos(-2900.0, 67, -5500.0, yaw=180), _pos(-3004.6, 67, -5579.6, yaw=90)])
    assert not ns.cursor_stats.get("shaft_stops")
    # a sprint-jumping servo at 0.35 a tick: the hole 3.5 blocks ahead is seen in time
    ns = _ns(g, [({"_goto": {}}, 1)])
    _walk(ns, [_pos(-3004.6, 67, z, yaw=180) for z in (-5576.3, -5576.65, -5577.0)])
    assert ns.cursor_stats.get("shaft_stops") == 1 and ns.queue == []
    # at the bottom of the shaft, walking out sideways: nothing to stop
    ns = _ns(g, [({"forward": 1}, 1)])
    _walk(ns, [_pos(-3004.5, 9, -5580.5, yaw=-90), _pos(-3004.3, 9, -5580.5, yaw=-90)])
    assert not ns.cursor_stats.get("shaft_stops") and ns.queue
    # a screen open: no walking, no guard
    ns = _ns(g, [({"forward": 1}, 1)])
    ns._gui_open = True
    _walk(ns, [_pos(-3004.6, 67, -5579.7, yaw=180)] * 2)
    assert not ns.cursor_stats.get("shaft_stops")
