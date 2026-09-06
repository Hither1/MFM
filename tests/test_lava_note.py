"""The LAVA AHEAD advice tells a sliver from a lake (agent.LAVA_SLIVER_FRAC).

ob1/ob1b (3%) and og4 (1%, 2026-09-07) poured on a sliver seen from afar and mined stone:
flowing lava turns to cobblestone. Below the threshold the note says so, keeps the
cells off the no-argument pour's record and asks for a closer, larger sighting; at
lake size the pour sentence stands.
"""
from types import SimpleNamespace

import numpy as np


def _advice(monkeypatch, frac):
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel import vision
    from mcu_worldmodel.agent import WorldModelAgent as A

    marks, remembered = [], []
    monkeypatch.setattr(vision, "lava_view", lambda frame: (frac, 320.0, 300.0, 250.0))
    monkeypatch.setattr(MN, "lava_cells", lambda pos, cx, bottom, top=None, min_dist=2.0:
                        {"pool": (-2992, 10, -5555), "rim": (-2992, 10, -5562), "dist": 6.0})
    monkeypatch.setattr(MN, "remember_lava", lambda cells, step, pos, source: remembered.append(cells))
    monkeypatch.setattr(MN, "lava_sentence", lambda cells: "The pool cell is (-2992, 10, -5555).")
    ns = SimpleNamespace(LAVA_SLIVER_FRAC=A.LAVA_SLIVER_FRAC, _cur_inv={"water_bucket": 1},
                         _obsidian_unmet=lambda: True, _last_pov=np.zeros((360, 640, 3), np.uint8),
                         step=100, cursor_stats={},
                         grid=SimpleNamespace(mark_lava=lambda *a: marks.append(a)))
    text = A._lava_advice(ns, {"x": -2991.0, "y": 11.0, "z": -5561.0, "yaw": 0.0, "pitch": 0.0})
    return text, marks, remembered, ns.cursor_stats


def test_a_sliver_is_named_and_kept_off_the_pour_record(monkeypatch):
    text, marks, remembered, stats = _advice(monkeypatch, 0.02)
    assert "SLIVER" in text and "do not pour on it" in text and "8%+" in text
    assert "THIS IS THE LAVA" not in text
    assert len(marks) == 1 and marks[0][3] == 0.02          # on the map, with its fraction
    assert remembered == [] and stats["lava_slivers"] == 1  # not on record for make_obsidian()


def test_a_lake_keeps_the_pour_sentence(monkeypatch):
    text, marks, remembered, stats = _advice(monkeypatch, 0.35)
    assert text.startswith("THIS IS THE LAVA THE OBSIDIAN NEEDS") and "SLIVER" not in text
    assert len(remembered) == 1 and len(marks) == 1 and "lava_slivers" not in stats


def test_the_second_stop_at_one_spot_says_so():
    from mcu_worldmodel.agent import WorldModelAgent as A

    ns = SimpleNamespace(_lava_stops={}, cursor_stats={})
    here = {"x": -2984.3, "y": 5.0, "z": -5567.6}
    assert A._lava_repeat_clause(ns, here) == ""
    second = A._lava_repeat_clause(ns, {"x": -2984.9, "y": 5.4, "z": -5567.9})   # same 3-block cell
    assert "REPEAT: this is the 2nd plan" in second and "do not target this spot again" in second
    assert "3rd plan" in A._lava_repeat_clause(ns, here)
    assert A._lava_repeat_clause(ns, {"x": -2960.0, "y": 5.0, "z": -5567.6}) == ""   # elsewhere
    assert ns.cursor_stats["lava_repeat_stops"] == 2
