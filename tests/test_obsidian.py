"""The obsidian macros after the 2026-09-06 fixes: a procedure with a tick floor is
dropped whole at the step cap instead of shrunk into a stub, make_obsidian /
mine_obsidian default to the last sighting's cells, and the closed-loop scoop and
mining ticks end on the inventory and the statistics, not on a tick count."""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np


def _agent(pos, inv, stats=None):
    """A stub with what the ticks read and write."""
    notes: list[str] = []
    marks: list = []                 # grid.mark_lava calls
    st = dict(stats or {})

    def stat_now(event, obj):
        return float(st.get(f"{event}.{obj}", 0.0))

    return SimpleNamespace(
        grid=SimpleNamespace(mark_lava=lambda *a, **kw: marks.append(a)), marks=marks,
        _gui_open=False, _cur_pos=dict(pos), _cur_inv=dict(inv), _log_breaks=0.0,
        _other_breaks=0.0, cursor_stats={}, step=100, stat_now=stat_now,
        memory=SimpleNamespace(add_note=notes.append), notes=notes, stats=st,
        _note_failure=lambda label: None,
        _flush_tail=lambda note, stat: notes.append(note))


def _run(tick, agent, payload, mk=None, limit=600):
    mk = mk or (lambda **kw: {"camera": [0.0, 0.0], **kw})
    acts = []
    for _ in range(limit):
        a = tick(agent, payload, mk)
        if a is None:
            return acts
        acts.append(a)
    raise AssertionError("tick never finished")


def test_find_lava_is_not_shrunk_below_its_floor():
    from mcu_worldmodel.actions import parse_actions
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"iron_pickaxe": 1, "water_bucket": 1})
    info["location_stats"]["ypos"] = np.array(11.0)
    plan = json.dumps({"actions": [{"procedure": "travel", "args": {"n": 300}},
                                   {"procedure": "find_lava", "args": {"n": 600}}]})
    out = parse_actions(plan, info=info, step_cap=400)
    assert [e["procedure"] for e in out.entries] == ["travel"]
    assert any("'find_lava' NOT STARTED" in n for n in out.notes), out.notes
    # With the budget it fits and keeps its floor.
    out = parse_actions(json.dumps({"actions": [{"procedure": "find_lava", "args": {"n": 600}}]}),
                        info=info, step_cap=400)
    assert out.entries and out.entries[0]["steps"] == 400


def test_obsidian_macros_default_to_the_sighting():
    from mcu_worldmodel import macros_nether as MN
    from mcu_worldmodel.testing import fake_info

    info = fake_info(inventory={"diamond_pickaxe": 1, "water_bucket": 1})
    pos = {"x": 0.5, "y": 64.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}
    MN.LAST_LAVA = None
    acts, note = MN.mine_obsidian(None, info)
    assert not acts and "no lava sighting" in note
    acts, note = MN.make_obsidian(None, info)
    assert not acts and "no lava sighting" in note
    acts, note = MN.mine_obsidian(None, info, x=1, y=None, z=3)
    assert not acts and "all three" in note

    cells = MN.lava_cells({**pos, "pitch": 30.0}, 0.0, 0.70)
    assert cells is not None
    MN.remember_lava(cells, 100, pos, "guard")
    acts, note = MN.mine_obsidian(None, info)
    m = next(a for a in acts if "_mineobs" in a)
    assert tuple(m["_mineobs"]["cell"]) == MN.LAST_LAVA["pool"] and m["_min"] == MN.MINEOBS_MIN
    assert "the last sighting's pool cell" in note
    acts, note = MN.make_obsidian(None, info)
    keys = [k for a in acts for k in a if k.startswith("_") and k not in ("_cost", "_min")]
    assert "_useat" in keys and "_scoop" in keys and "_obsidiancheck" in keys
    assert keys[0] == "_backoff" and tuple(acts[0]["_backoff"]["pool"]) == MN.LAST_LAVA["pool"]
    assert acts[0]["_backoff"]["approach"] == (not MN.LAST_LAVA["clipped"])
    s = next(a for a in acts if "_scoop" in a)
    r = MN.LAST_LAVA["rim"]
    assert tuple(s["_scoop"]["cell"]) == (r[0], r[1] + 1, r[2]) and s["_min"] == MN.SCOOP_MIN
    # A pour by coordinates with no lava in view and no sighting is blind: refused.
    MN.LAST_LAVA = None
    acts, note = MN.make_obsidian(None, info, x=-2992, y=10, z=-5561)
    assert not acts and "would be blind" in note
    # With lava in the frame it goes, and it is a sighting too: mine_obsidian() then
    # aims at that cell.
    lit = dict(info)
    lit["pov"] = np.zeros((360, 640, 3), dtype=np.uint8)
    lit["pov"][200:, :, 0] = 240
    lit["pov"][200:, :, 1] = 120
    lit["pov"][200:, :, 2] = 20
    assert MN._lava_now(lit) >= MN.LAVA_SEEN_FRAC, MN._lava_now(lit)
    acts, note = MN.make_obsidian(None, lit, x=-2992, y=10, z=-5561)
    assert acts and MN.LAST_LAVA["source"] == "pour" and MN.LAST_LAVA["pool"] == (-2992, 10, -5561)
    acts, note = MN.mine_obsidian(None, info)
    m = next(a for a in acts if "_mineobs" in a)
    assert tuple(m["_mineobs"]["cell"]) == (-2992, 10, -5561)
    # A guard re-sighting AFTER the pour does not move the target: the pour's pool
    # cell comes first, then the cell beyond it along the pour's bearing, then the rim.
    cells = MN.lava_cells({**pos, "pitch": 30.0}, 0.0, 0.70)
    MN.remember_lava(cells, 100, pos, "guard")
    acts, note = MN.make_obsidian(None, lit)
    pour_pool, pour_rim = MN.LAST_POUR["pool"], MN.LAST_POUR["rim"]
    MN.remember_lava({"pool": pour_rim, "rim": (pour_rim[0], pour_rim[1], pour_rim[2] - 1),
                      "dist": 2.0}, 120, pos, "guard")
    acts, note = MN.mine_obsidian(None, info)
    m = next(a for a in acts if "_mineobs" in a)
    assert tuple(m["_mineobs"]["cell"]) == pour_pool and "the last pour's pool cell" in note
    assert [tuple(c) for c in m["_mineobs"]["more"]][-1] == pour_rim
    MN.LAST_LAVA = None
    MN.LAST_POUR = None


def test_mineobs_tick_holds_the_aim_and_ends_on_the_statistic():
    from mcu_worldmodel import macros_nether as MN

    cell = (0, 62, 3)
    agent = _agent({"x": 0.5, "y": 64.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0},
                   {"diamond_pickaxe": 1})
    st = {"cell": list(cell), "t": 0, "n": 300, "phase": "aim", "base_obs": None,
          "base_inv": None, "base_breaks": None, "held": 0, "label": "mine_obsidian"}
    tick = MN.macros.TICKS["_mineobs"]
    # Aiming: camera only, no swing at the wrong block.
    a = tick(agent, st, lambda **kw: {"camera": [0.0, 0.0], **kw})
    assert a.get("attack") is None and a["camera"][0] > 0
    # Aimed: the attack key is held; a statistic that moves ends it.
    agent._cur_pos.update({"pitch": 42.2, "yaw": 0.0})      # atan((65.62-62.9)/3)
    for _ in range(3):
        a = tick(agent, st, lambda **kw: {"camera": [0.0, 0.0], **kw})
        assert a["attack"] == 1
    agent.stats["mine_block.obsidian"] = 1.0
    assert tick(agent, st, lambda **kw: {"camera": [0.0, 0.0], **kw}) is None
    assert any("OBSIDIAN BROKEN at (0, 62, 3)" in n and "HOLE over the pool" in n
               and 'place_at(x=0, y=62, z=3, item="cobblestone"' in n for n in agent.notes)
    assert agent.cursor_stats["obsidian_mined"] == 1
    assert agent.grid.mark_lava and agent.marks[-1][1] == (0, 62, 3)     # on the map as lava

    # The rim in front breaks first: the swing goes on (re-aimed); the third foreign
    # block ends it with the diagnosis.
    agent = _agent({"x": 0.5, "y": 64.0, "z": 0.5, "pitch": 42.2, "yaw": 0.0}, {})
    st = {"cell": list(cell), "t": 0, "n": 300, "phase": "aim", "base_obs": None,
          "base_inv": None, "base_breaks": None, "held": 0, "label": "mine_obsidian"}
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    tick(agent, st, mk)
    agent._log_breaks = 1.0
    assert tick(agent, st, mk) is not None and st["phase"] == "aim"
    assert any("in the way broke first" in n for n in agent.notes)
    assert tick(agent, st, mk)["attack"] == 1
    agent._other_breaks = 2.0
    assert tick(agent, st, mk) is None
    assert any("none was obsidian" in n for n in agent.notes)
    # With candidates left, the third foreign break moves the aim to the next cell.
    agent = _agent({"x": 0.5, "y": 64.0, "z": 0.5, "pitch": 42.2, "yaw": 0.0}, {})
    st = {"cell": list(cell), "t": 0, "n": 300, "phase": "aim", "base_obs": None,
          "base_inv": None, "base_breaks": None, "held": 0, "label": "mine_obsidian",
          "more": [[0, 62, 4]]}
    tick(agent, st, mk)
    agent._log_breaks = 3.0
    a = tick(agent, st, mk)
    assert a is not None and st["cell"] == [0, 62, 4] and not st["more"]
    assert any("trying the next cell of the pour, (0, 62, 4)" in n for n in agent.notes)

    # Out of reach: walks toward the cell first (the pour backed the avatar off);
    # a walk that never gets there ends with the note.
    agent = _agent({"x": 0.5, "y": 64.0, "z": -6.0, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"cell": list(cell), "t": 0, "n": 300, "phase": "aim", "base_obs": None,
          "base_inv": None, "base_breaks": None, "held": 0, "label": "mine_obsidian"}
    a = tick(agent, st, mk)
    assert a.get("forward") == 1 and st["t"] == 0
    for _ in range(5):
        a = tick(agent, st, mk)
    assert a.get("forward") == 1 and a.get("jump") == 1          # stalled: jumping
    agent._cur_pos["z"] = 0.5                                     # 4.05 from the eye now
    a = tick(agent, st, mk)
    assert "forward" not in a and st["phase"] == "aim"
    agent = _agent({"x": 0.5, "y": 64.0, "z": -6.0, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"cell": list(cell), "t": 0, "n": 300, "phase": "aim", "base_obs": None,
          "base_inv": None, "base_breaks": None, "held": 0, "label": "mine_obsidian"}
    for _ in range(MN.MINEOBS_WALK_TICKS + 1):
        a = tick(agent, st, mk)
    assert a is None and any("out of reach" in n for n in agent.notes)


def test_backoff_faces_the_pool_and_walks_back():
    from mcu_worldmodel import macros_nether as MN

    tick = MN.macros.TICKS["_backoff"]
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    # Pool 2 blocks ahead (+z), facing it: back until 3.5 from it and 1 block moved.
    agent = _agent({"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"pool": [0, 11, 2], "t": 0, "n": 60, "start": None, "last": None, "stall": 0,
          "label": "make_obsidian"}
    a = tick(agent, st, mk)
    assert a.get("back") == 1
    agent._cur_pos["z"] = -0.2                 # 2.7 from the pool centre: not yet
    assert tick(agent, st, mk).get("back") == 1
    agent._cur_pos["z"] = -1.2                 # 3.7 from the pool, 1.7 moved: done
    assert tick(agent, st, mk) is None
    assert any("backed off 1.7 blocks" in n for n in agent.notes)
    # Facing away from the pool: turns first, no step.
    agent = _agent({"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 180.0}, {})
    st = {"pool": [0, 11, 2], "t": 0, "n": 60, "start": None, "last": None, "stall": 0,
          "label": "make_obsidian"}
    a = tick(agent, st, mk)
    assert "back" not in a and abs(a["camera"][1]) > 12
    # A measured (unclipped) sighting 8 blocks off: the tick walks UP to the band.
    agent = _agent({"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"pool": [0, 11, 8], "t": 0, "n": 60, "start": None, "last": None, "stall": 0,
          "approach": True, "label": "make_obsidian"}
    a = tick(agent, st, mk)
    assert a.get("forward") == 1 and "back" not in a
    agent._cur_pos["z"] = 4.6                  # 3.9 from the pool centre: in the band
    assert tick(agent, st, mk) is None
    # A clipped sighting never walks up, even from far.
    agent = _agent({"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"pool": [0, 11, 8], "t": 0, "n": 60, "start": None, "last": None, "stall": 0,
          "approach": False, "label": "make_obsidian"}
    assert tick(agent, st, mk).get("back") == 1
    # A wall behind: eight stalled ticks end it with the note.
    agent = _agent({"x": 0.5, "y": 12.0, "z": 0.5, "pitch": 0.0, "yaw": 0.0}, {})
    st = {"pool": [0, 11, 2], "t": 0, "n": 60, "start": None, "last": None, "stall": 0,
          "label": "make_obsidian"}
    out = [tick(agent, st, mk) for _ in range(20)]
    assert None in out and any("blocks the way back" in n for n in agent.notes)


def test_scoop_tick_walks_back_and_presses_until_the_bucket_reads_water():
    from mcu_worldmodel import macros_nether as MN

    tick = MN.macros.TICKS["_scoop"]
    cell = [0, 63, 3]
    # Pushed 6 blocks off: walks first, aims, presses; the inventory ends it.
    agent = _agent({"x": 0.5, "y": 64.0, "z": -5.5, "pitch": 0.0, "yaw": 0.0}, {"bucket": 1})
    st = {"cell": cell, "t": 0, "n": 120, "phase": "walk", "presses": 0, "base_wb": None,
          "hold": 0, "label": "make_obsidian"}
    mk = lambda **kw: {"camera": [0.0, 0.0], **kw}
    a = tick(agent, st, mk)
    assert a.get("forward") == 1 and st["phase"] == "walk"
    for _ in range(5):                            # no progress: the walk starts jumping
        a = tick(agent, st, mk)
    assert a.get("forward") == 1 and a.get("jump") == 1
    agent._cur_pos["z"] = 1.0                     # 3.1 from the cell's top: near enough
    a = tick(agent, st, mk)
    assert a.get("forward") is None and st["phase"] == "aim"
    agent._cur_pos.update({"pitch": 36.1, "yaw": 0.0})      # atan((65.62-63.8)/2.5)
    pressed = [tick(agent, st, mk) for _ in range(8)]
    assert any(p.get("use") == 1 for p in pressed) and st["presses"] >= 1
    agent._cur_inv["water_bucket"] = 1
    assert tick(agent, st, mk) is None
    assert any("back in the bucket" in n for n in agent.notes)
    # Budget spent: the note names the cell and the call to make by hand.
    agent = _agent({"x": 0.5, "y": 64.0, "z": 1.0, "pitch": 36.1, "yaw": 0.0}, {"bucket": 1})
    st = {"cell": cell, "t": 0, "n": 12, "phase": "walk", "presses": 0, "base_wb": None,
          "hold": 0, "label": "make_obsidian"}
    _run(tick, agent, st, mk)
    assert any("NOT scooped back" in n and "use_at(0, 63, 3" in n for n in agent.notes)


def test_dig_refusal_names_the_way_out():
    from mcu_worldmodel.agent import WorldModelAgent

    stub = SimpleNamespace(_last_water_seen=(90, 10.0, 10.0), step=100,
                           _cur_pos={"x": 12.0, "y": 64.0, "z": 10.0, "yaw": 0.0},
                           DIG_WATER_STEPS=WorldModelAgent.DIG_WATER_STEPS,
                           DIG_WATER_BLOCKS=WorldModelAgent.DIG_WATER_BLOCKS)
    note = WorldModelAgent._dig_water_refusal(stub, "dig_down")
    assert note and "go_to(x=18.0, z=10.0, within=1, n=120)" in note
