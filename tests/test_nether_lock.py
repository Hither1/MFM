"""The Nether lock (agent._nether_lock): in the Nether a plan action that moves
gets sneak, loses sprint, and loses a jump taken while moving; a vertical jump keeps it;
nothing changes with a screen open, outside the Nether, or without the runner's reflexes.
Every Nether visit on record (four visits, three lives) died walking, sprinting or jumping off a
ledge into the lava sea."""
from __future__ import annotations

from types import SimpleNamespace


def _agent(dimension="the Nether", reflexes=True, gui=False):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    ns = SimpleNamespace(_dimension=dimension, reflexes=reflexes, _gui_open=gui,
                         cursor_stats={}, _nether_lock_noted=False, notes=notes,
                         memory=SimpleNamespace(add_note=notes.append),
                         NETHER_MOVE_KEYS=A.NETHER_MOVE_KEYS)
    ns.lock = lambda a: A._nether_lock(ns, a)
    return ns


def test_moving_actions_sneak_and_lose_sprint_and_jump():
    from mcu_worldmodel.procedures import act

    ns = _agent()
    a = ns.lock(act(forward=1, sprint=1, jump=1, camera=[3.0, -4.0]))
    assert a["forward"] == 1 and a["sneak"] == 1 and a["sprint"] == 0 and a["jump"] == 0
    assert a["camera"] == [3.0, -4.0]
    assert ns.cursor_stats == {"nether_lock_jumps": 1, "nether_lock_ticks": 1}
    assert len(ns.notes) == 1 and ns.notes[0].startswith("NETHER LOCK:")
    assert "lava sea at y ~31" in ns.notes[0] and "stair_down" in ns.notes[0]
    assert "NETHER DESCENT" in ns.notes[0] and "cannot step off" not in ns.notes[0]
    b = ns.lock(act(back=1, sprint=1))
    assert b["back"] == 1 and b["sneak"] == 1 and b["sprint"] == 0 and b["jump"] == 0
    assert len(ns.notes) == 1 and ns.cursor_stats["nether_lock_ticks"] == 2     # one note per visit


def test_vertical_jump_and_still_actions_pass():
    from mcu_worldmodel.procedures import act, noop

    ns = _agent()
    pillar = ns.lock(act(jump=1, use=1))                    # pillar_up's tick
    assert pillar["jump"] == 1 and pillar["use"] == 1 and pillar["sneak"] == 0
    assert ns.lock(act(attack=1)) == act(attack=1)
    assert ns.lock(noop()) == noop()
    cam = act(camera=[0.0, 20.0])
    assert ns.lock(cam) == cam
    assert ns.notes == [] and ns.cursor_stats == {}
    sprint_only = ns.lock(act(sprint=1))                    # a sprint key alone is dropped too
    assert sprint_only["sprint"] == 0 and sprint_only["sneak"] == 0


def test_lock_is_nether_only_reflexes_only_world_only():
    from mcu_worldmodel.procedures import act

    walk = act(forward=1, sprint=1, jump=1)
    assert _agent(dimension="the Overworld").lock(walk) == walk
    assert _agent(dimension="the End").lock(walk) == walk
    assert _agent(reflexes=False).lock(walk) == walk          # --human-play
    assert _agent(gui=True).lock(walk) == walk                # sneak + click is the quick-move
    ns = _agent()
    ns.lock(walk)
    assert ns._nether_lock_noted is True
    ns._dimension = "the Overworld"                           # a death puts it back
    ns.lock(walk)
    assert ns._nether_lock_noted is False


def test_explore_budget_rebased_under_the_lock():
    from mcu_worldmodel import macros_nether as MN

    assert MN.EXPLORE_TICKS_PER_BLOCK_LOCKED > MN.EXPLORE_TICKS_PER_BLOCK
    st = {"budget": 24 * MN.EXPLORE_TICKS_PER_BLOCK + 120, "length": 24, "used": 0,
          "start": None, "y0": None, "min_y": None, "base_breaks": 0, "ax": 1, "az": 0,
          "yaw_t": -90.0, "lava": 0.0, "phase": "walk", "phase_t": 0, "stuck": 0,
          "block": None, "bridges": 0, "broken": 0}
    notes: list[str] = []
    agent = SimpleNamespace(_gui_open=False, _cur_pos={"x": 0.0, "y": 60.0, "z": 0.0,
                                                       "pitch": 8.0, "yaw": -90.0},
                            _log_breaks=0, _other_breaks=0, _dimension="the Nether",
                            reflexes=True, _last_pov=None, step=1, cursor_stats={},
                            memory=SimpleNamespace(add_note=notes.append))
    MN._nexplore_tick(agent, st, lambda **kw: dict(kw))
    assert st["locked"] is True
    assert st["budget"] == 24 * MN.EXPLORE_TICKS_PER_BLOCK_LOCKED + 120
    st2 = dict(st, locked=False, budget=10, start=None)
    agent._dimension = "the Overworld"
    MN._nexplore_tick(agent, st2, lambda **kw: dict(kw))
    assert st2["budget"] == 10 and not st2.get("locked")


def _descent_agent(dimension="the Nether", entry="raw", queue=None, reflex=None, pov=True):
    from mcu_worldmodel.agent import WorldModelAgent as A

    notes: list[str] = []
    q = [({"forward": 1}, 0), ({"forward": 1}, 0)] if queue is None else queue
    ns = SimpleNamespace(_dimension=dimension, reflexes=True, _gui_open=False,
                         cursor_stats={}, notes=notes, queue=q, _reflex=reflex,
                         _last_pov=None, _nether_lava=0.0,
                         _entry_start_pos={"x": 0.0, "y": 40.0, "z": 0.0},
                         _entry_index=0, _plan_entries=[{"procedure": entry} if entry != "raw"
                                                        else {"repeat": 2}],
                         memory=SimpleNamespace(add_note=notes.append),
                         NETHER_DESCENT_OK=A.NETHER_DESCENT_OK,
                         NETHER_DESCENT_MIN=A.NETHER_DESCENT_MIN)
    return ns


def _run_descent(ns, ys, lava, step0=100):
    from mcu_worldmodel import vision
    from mcu_worldmodel.agent import WorldModelAgent as A

    orig = vision.lava_fraction
    vision.lava_fraction = lambda frame: lava
    try:
        ns._last_pov = __import__("numpy").zeros((4, 4, 3), dtype="uint8")
        for i, y in enumerate(ys):
            A._nether_descent_guard(ns, step0 + 4 * i, {"x": 0.0, "y": y, "z": float(i),
                                                        "pitch": 8.0, "yaw": 0.0})
    finally:
        vision.lava_fraction = orig


def test_descent_guard_drops_a_walk_down_toward_lava():
    ns = _descent_agent()
    _run_descent(ns, [40.0, 39.6, 39.0], lava=0.24)
    assert ns.queue == [] and ns.cursor_stats == {"nether_descents": 1}
    assert len(ns.notes) == 1 and ns.notes[0].startswith("NETHER DESCENT: this entry (raw) walked you 1 block(s) DOWN to (0, 39, 2)")
    assert "24% of the lower view" in ns.notes[0] and "2 action(s)" in ns.notes[0] and "stair_down" in ns.notes[0]
    # no lava in view: a walk down a dark slope is not this guard's (the fall guard's)
    ns = _descent_agent()
    _run_descent(ns, [40.0, 39.0, 37.0], lava=0.0)
    assert len(ns.queue) == 2 and ns.notes == []
    # less than a block down: quiet
    ns = _descent_agent()
    _run_descent(ns, [40.0, 39.5], lava=0.5)
    assert len(ns.queue) == 2 and ns.notes == []
    # a dug descent, the Overworld, an empty queue, an escape in progress: quiet
    for ns in (_descent_agent(entry="stair_down"), _descent_agent(dimension="the Overworld"),
               _descent_agent(queue=[]), _descent_agent(reflex={"kind": "lava"})):
        _run_descent(ns, [40.0, 38.0], lava=0.5)
        assert ns.notes == []


def test_contract_names_the_lock():
    from mcu_worldmodel import prompts

    assert "**The Nether lock.**" in prompts._SURVIVAL_RULE
    assert "**The Nether lock.**" in prompts._SURVIVAL_GENERIC
    assert "NETHER DESCENT" in prompts._SURVIVAL_RULE and "cannot step off" not in prompts._SURVIVAL_RULE
