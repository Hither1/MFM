"""The lava escape walks back along the trail (agent._lava_home / _lava_tick).
One run: the first lava hit got the 180-degree turn, the runner's `back`
step then walked the avatar deeper into the pool; one run got the bunker and dug INTO the
pool. Three of the day's four deaths were at the pool the run had just found."""
from __future__ import annotations

from types import SimpleNamespace


def _ns(pos, walked, hazard=(), lava=(), wb=4):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    ns = SimpleNamespace(
        LAVA_OUT_TICKS=A.LAVA_OUT_TICKS, LAVA_OUT_MAX=A.LAVA_OUT_MAX,
        _cur_pos=dict(pos), _cur_inv={"water_bucket": 1} if wb else {}, _gui_open=False,
        _dimension="the Overworld", _last_health=16.0, cursor_stats={}, notes=notes,
        memory=SimpleNamespace(add_note=notes.append), stat_now=lambda a, b: 0.0,
        grid=SimpleNamespace(walked=walked, hazard=set(hazard), lava=set(lava)), step=500)
    ns._water_slot = lambda info: wb
    ns._lava_home = lambda pos: A._lava_home(ns, pos)
    ns._lava_home_cell = lambda pos: A._lava_home_cell(ns, pos)
    ns._finish_lava = lambda rf, why: A._finish_lava(ns, rf, why)
    return ns


def test_lava_home_is_the_last_dry_cell_a_block_away():
    from mcu_worldmodel.agent import WorldModelAgent as A

    # a trail along +x at y 11 into a pool: the last cells were walked in the lava
    walked = {(x, 11, 0): {"first": 10 * x, "last": 10 * x, "n": 1} for x in range(-4, 2)}
    walked[(3, 10, 0)] = {"first": 60, "last": 62, "n": 1}       # in the pool (hurt there)
    pos = {"x": 3.5, "y": 10.0, "z": 0.5, "pitch": 0.0, "yaw": -90.0}
    ns = _ns(pos, walked, hazard=[(3, 10, 0)])
    assert A._lava_home(ns, pos) == (1.5, 0.5)                    # the rim cell, not the pool
    # a cell below the avatar is never home (a hole it fell through)
    walked[(2, 8, 0)] = {"first": 70, "last": 70, "n": 1}
    assert A._lava_home(ns, pos) == (1.5, 0.5)
    # nothing walked within reach: no home, the old back-step stands
    assert A._lava_home(ns, {**pos, "x": 30.5}) is None


def test_lava_escape_turns_toward_the_trail_and_walks():
    from mcu_worldmodel.agent import WorldModelAgent as A

    walked = {(x, 11, 0): {"first": 10 * x, "last": 10 * x, "n": 1} for x in range(-4, 2)}
    # facing +x (yaw -90), away from the trail -- the case after the turn
    pos = {"x": 3.5, "y": 10.0, "z": 0.5, "pitch": 0.0, "yaw": -90.0}
    ns = _ns(pos, walked)
    rf = A._arm_lava(ns, {}, pos, 16.0, 0.3)
    assert rf["home"] == (1.5, 0.5) and rf["phase"] == "equip"
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    a = A._lava_tick(ns, rf, mk)
    assert a.get("hotbar_4") == 1                                  # the bucket
    for _ in range(3):                                             # look straight down
        a = A._lava_tick(ns, rf, mk)
        ns._cur_pos["pitch"] = min(90.0, ns._cur_pos["pitch"] + a["camera"][0])
    a = A._lava_tick(ns, rf, mk)
    assert a.get("use") == 1 and rf["phase"] == "pour"
    A._lava_tick(ns, rf, mk)
    A._lava_tick(ns, rf, mk)
    # out: the yaw turns toward -x (yaw 90) with the jump held, nothing forward yet
    a = A._lava_tick(ns, rf, mk)
    assert rf["phase"] == "out" and a.get("jump") == 1 and "forward" not in a
    assert abs(a["camera"][1]) == 30.0 and a["camera"][0] < 0        # turning, levelling
    for _ in range(8):
        ns._cur_pos["yaw"] += a["camera"][1]
        ns._cur_pos["pitch"] += a["camera"][0]
        a = A._lava_tick(ns, rf, mk)
        if a.get("forward"):
            break
    off = ((ns._cur_pos["yaw"] - 90.0 + 180.0) % 360.0) - 180.0
    assert a.get("forward") == 1 and a.get("jump") == 1 and abs(off) < 30
    # arriving on the trail ends the walk
    ns._cur_pos.update({"x": 1.6, "z": 0.5})
    a = A._lava_tick(ns, rf, mk)
    assert rf["phase"] == "level"
    while A._lava_tick(ns, rf, mk) is not None:
        pass
    assert any("back toward the ground you came from, (1.5, 0.5)" in n for n in ns.notes)


def test_lava_escape_without_a_trail_steps_back():
    from mcu_worldmodel.agent import WorldModelAgent as A

    pos = {"x": 3.5, "y": 10.0, "z": 0.5, "pitch": 0.0, "yaw": -90.0}
    ns = _ns(pos, {}, wb=None)
    rf = A._arm_lava(ns, {}, pos, 16.0, 0.3)
    assert rf["home"] is None and rf["phase"] == "out"
    a = A._lava_tick(ns, rf, lambda **kw: {"camera": [0.0, 0.0], **kw})
    assert a.get("back") == 1 and a.get("jump") == 1
