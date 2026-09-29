"""The lava guard's cooldown ends with the plan entry it stopped (agent._lava_guard).
One run: LAVA AHEAD fired during Action 617 (mine_obsidian, action_num 616);
the next plan's first entry, go_to west (Action 618, action_num 617), ran 30 ticks later
inside the old `action_num <= last + 1` window unguarded, and the avatar burned to death
with 5 obsidian."""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import numpy as np


def _ns(action_num):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    return SimpleNamespace(
        _pos_hist=deque(maxlen=5), _gui_open=False, _last_pov=np.zeros((8, 8, 3), np.uint8),
        queue=[({"_goto": {}}, 1), ({"forward": 1}, 1)], LAVA_GUARD_EXEMPT=A.LAVA_GUARD_EXEMPT,
        _last_lava_step=-1000, _last_lava_frac=0.0, _last_lava_action=-1,
        action_num=action_num, cursor_stats={}, _reflex=None, structured=False, notes=notes,
        _keep_event_frame=lambda *a: None, _encode_pov=lambda *a: None,
        memory=SimpleNamespace(save_frame=lambda *a, **k: None, add_note=notes.append),
        _lava_advice=lambda pos: "advice.", _lava_repeat_clause=lambda pos, frac=0.0: "")


def _pos(x, z):
    return {"x": float(x), "y": 12.0, "z": float(z), "pitch": 0.0, "yaw": 0.0}


def test_the_next_entry_is_guarded_again(monkeypatch):
    from mcu_worldmodel import vision
    from mcu_worldmodel.agent import WorldModelAgent as A

    monkeypatch.setattr(vision, "lava_fraction", lambda arr: 0.5)
    ns = _ns(action_num=616)
    A._lava_guard(ns, 14284, _pos(-2988.0, -5558.5))          # first sample: nothing to compare
    A._lava_guard(ns, 14288, _pos(-2988.4, -5558.5))          # moved 0.4 with lava in view
    assert ns.cursor_stats.get("lava_flagged") == 1 and ns.queue == []
    assert ns._last_lava_action == 616 and any("LAVA AHEAD" in n for n in ns.notes)
    # the same entry (the queue refilled by a reflex, say) stays in the cooldown
    ns.queue = [({"forward": 1}, 1)]
    A._lava_guard(ns, 14292, _pos(-2988.8, -5558.5))
    assert ns.cursor_stats["lava_flagged"] == 1 and ns.queue
    # the stopped entry closed (action_num 617); the next plan's FIRST entry walks on:
    # One run's go_to -- it must be stopped again, 8 ticks into the old 150-tick window
    ns.action_num = 617
    ns.queue = [({"_goto": {}}, 1), ({"forward": 1}, 1)]
    A._lava_guard(ns, 14296, _pos(-2989.2, -5558.5))
    assert ns.cursor_stats["lava_flagged"] == 2 and ns.queue == []
    assert ns._last_lava_action == 617


def test_repeat_clause_yields_to_a_growing_sighting_with_the_bucket():
    from mcu_worldmodel.agent import WorldModelAgent as A

    ns = SimpleNamespace(_lava_stops={}, cursor_stats={}, _cur_inv={"water_bucket": 1},
                         _obsidian_unmet=lambda: True)
    pos = {"x": -2998.0, "y": 12.0, "z": -5554.0}
    assert A._lava_repeat_clause(ns, pos, 0.02) == ""                 # One run step 5764
    c = A._lava_repeat_clause(ns, pos, 0.04)                           # step 5820: it grew
    assert c.startswith(" CLOSER") and "GREW from 2% to 4%" in c and "do not turn away" in c
    assert ns.cursor_stats == {"lava_closer": 1}
    r = A._lava_repeat_clause(ns, pos, 0.04)                           # the same sliver again
    assert r.startswith(" REPEAT") and "3rd plan" in r and ns.cursor_stats["lava_repeat_stops"] == 1
    ns2 = SimpleNamespace(_lava_stops={}, cursor_stats={}, _cur_inv={}, _obsidian_unmet=lambda: True)
    A._lava_repeat_clause(ns2, pos, 0.02)
    assert A._lava_repeat_clause(ns2, pos, 0.30).startswith(" REPEAT")   # no bucket: leave
