"""explore_nether(bearing=...) walks along a yaw instead of an axis -- the walk TOWARD a
fortress sighting. og9_mfm 2026-09-07 step 17727: "FORTRESS IN VIEW ... bearing yaw 61",
the model turned, tunnelled 1.2 blocks, stalled and went west along the axis; the only
fortress any run has seen was never approached."""
from __future__ import annotations

import math
from types import SimpleNamespace


def _inv():
    from mcu_worldmodel.testing import fake_info
    return fake_info(inventory={"diamond_pickaxe": 1, "cobblestone": 40})


def test_bearing_sets_the_heading_and_the_direction_vector():
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel import macros_world as MW
    from mcu_worldmodel.cursor import CursorState

    acts, note = MN.explore_nether(CursorState(), _inv(), bearing=61, length=40)
    assert acts and "along bearing 61 (yaw 61)" in note
    st = acts[-1]["_nexplore"]
    assert st["yaw_t"] == 61 and st["dir_txt"] == "bearing 61" and st["length"] == 40
    ax, az = MW.facing(61.0)
    assert math.isclose(st["ax"], ax) and math.isclose(st["az"], az)
    # a bearing wins over an axis; it is normalised; the axis path is unchanged
    acts, note = MN.explore_nether(CursorState(), _inv(), axis="x", sign=-1, bearing=300)
    assert acts[-1]["_nexplore"]["yaw_t"] == -60 and "bearing -60" in note
    acts, note = MN.explore_nether(CursorState(), _inv(), axis="x", sign=-1, length=50)
    assert acts[-1]["_nexplore"]["yaw_t"] == 90 and "along x- (yaw 90)" in note
    assert acts[-1]["_nexplore"]["dir_txt"] == "x-"
    acts, note = MN.explore_nether(CursorState(), _inv(), bearing="north")
    assert not acts and "bearing must be a yaw" in note


def test_finish_note_names_the_bearing_and_the_sighting_says_how_to_approach():
    from mcu_worldmodel import macros_nether as MN

    notes: list[str] = []
    agent = SimpleNamespace(_cur_pos={"x": -362.0, "y": 43.0, "z": -688.0, "yaw": 61.0},
                            cursor_stats={}, memory=SimpleNamespace(add_note=notes.append))
    st = {"start": (-362.0, -688.0), "ax": MN.MW.facing(61.0)[0], "az": MN.MW.facing(61.0)[1],
          "length": 40, "used": 12, "broken": 0, "bridges": 0, "lava": 0.0,
          "axis": "bearing", "sign": 1, "dir_txt": "bearing 61"}
    MN._nexplore_finish(agent, st, "Done.")
    assert notes and notes[0].startswith("explore_nether(bearing 61): walked 0 of 40 blocks")
    import inspect
    src = inspect.getsource(MN._nexplore_tick)
    assert "explore_nether(bearing={bearing:.0f}, length=40) walks TOWARD it" in src
    assert "travel/go_to toward it" not in src
