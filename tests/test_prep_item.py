"""An item named by a plan entry is brought to hand when the entry RUNS, not when the plan
is parsed: every entry is expanded before the first one runs, and an earlier entry's
inventory trip moves stacks. One life's pillar "of cobblestone" was its last three
obsidian (the trip compiled at parse time swapped the two stacks back)."""
from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import numpy as np

from mcu_worldmodel import macros, macros_world as MW
from mcu_worldmodel.testing import fake_info


def _info(slots: dict[int, tuple[str, int]]) -> dict:
    info = fake_info()
    for s, (name, q) in slots.items():
        info["inventory"][s] = {"type": name, "quantity": np.array(q)}
    return info


# the recorded turn: tools in the hotbar, obsidian in slot 5, the cobblestone in the pack
TOOLS = {0: ("diamond_pickaxe", 1), 1: ("diamond_sword", 1), 2: ("iron_pickaxe", 1),
         3: ("stone_pickaxe", 1), 4: ("flint_and_steel", 1), 6: ("iron_pickaxe", 1),
         7: ("bucket", 1), 8: ("furnace", 2)}
AT_PARSE = {**TOOLS, 5: ("obsidian", 3), 20: ("cobblestone", 55)}
AFTER_PLACE_AT = {**TOOLS, 5: ("cobblestone", 55), 20: ("obsidian", 3)}   # its trip swapped them


def _agent(info):
    from mcu_worldmodel.cursor import CursorState as Cursor
    notes: list[str] = []
    a = SimpleNamespace(_cur_info=info, cursor=Cursor(), queue=deque(), cursor_stats={},
                        notes=notes, memory=SimpleNamespace(add_note=notes.append),
                        _note_failure=lambda label: None, _gui_open=False)
    a._flush_tail = lambda note, stat: (notes.append(note), a.cursor_stats.update({stat: 1}))
    return a


def _hotbar_keys(steps) -> list[str]:
    return [k for s, _ in steps for k in s if k.startswith("hotbar") and s[k]]


def test_the_prep_is_one_marker_and_costs_what_the_trip_cost():
    from mcu_worldmodel.cursor import CursorState as Cursor
    acts, err = MW._prep_item(Cursor(), _info(AT_PARSE), "cobblestone", "pillar_up")
    assert err == "" and len(acts) == 1 and macros.kind_of(acts[0]) == "_prep"
    assert acts[0]["_prep"] == {"item": "cobblestone", "label": "pillar_up"}
    assert acts[0]["_cost"] > 2                      # the inventory trip, charged at parse time
    acts, _ = MW._prep_item(Cursor(), _info(AFTER_PLACE_AT), "cobblestone", "pillar_up")
    assert acts[0]["_cost"] == 2                     # in the hotbar: the key and its settle tick
    assert MW._prep_item(Cursor(), _info(AT_PARSE), "dirt", "pillar_up") == (
        [], "pillar_up: you carry no dirt.")


def test_a_stack_an_earlier_entry_moved_is_selected_where_it_is_now():
    """The recorded plan: compiled when the cobblestone was in the pack, run after
    place_at had swapped it into the obsidian's hotbar slot. No second trip, and the key
    pressed is the cobblestone's slot."""
    from mcu_worldmodel.cursor import CursorState as Cursor
    acts, _ = MW._prep_item(Cursor(), _info(AT_PARSE), "cobblestone", "pillar_up")
    agent = _agent(_info(AFTER_PLACE_AT))
    agent.queue.extend([(acts[0], 3), ({"_pillar": {}}, 3)])
    assert MW._prep_tick(agent, acts[0]["_prep"], None) is None
    spliced = list(agent.queue)[1:-1]
    assert _hotbar_keys(spliced) == ["hotbar.6"] and len(spliced) == 2     # no screen opened
    assert all(idx == 3 for _, idx in spliced) and "_pillar" in agent.queue[-1][0]
    assert agent.notes == []


def test_the_trip_is_made_from_the_slots_of_the_tick_it_runs_on():
    """Nothing moved: the same trip as before, compiled at run time."""
    from mcu_worldmodel.cursor import CursorState as Cursor
    info = _info(AT_PARSE)
    old, hot, err = __import__("mcu_worldmodel.macros_gui", fromlist=["x"]).ensure_hotbar(
        Cursor(), info, "cobblestone", "pillar_up")
    acts, _ = MW._prep_item(Cursor(), info, "cobblestone", "pillar_up")
    agent = _agent(info)
    agent.queue.append((acts[0], 0))
    MW._prep_tick(agent, acts[0]["_prep"], None)
    spliced = list(agent.queue)[1:]
    assert len(spliced) == len(old) + 2 and _hotbar_keys(spliced) == [f"hotbar.{hot + 1}"]
    assert any("_screen_need" in s for s, _ in spliced)


def test_an_item_that_is_gone_stops_the_plan_and_nothing_else_is_used():
    from mcu_worldmodel.cursor import CursorState as Cursor
    acts, _ = MW._prep_item(Cursor(), _info(AT_PARSE), "cobblestone", "pillar_up")
    gone = {**TOOLS, 5: ("obsidian", 3)}
    agent = _agent(_info(gone))
    agent.queue.extend([(acts[0], 3), ({"_pillar": {}}, 3)])
    assert MW._prep_tick(agent, acts[0]["_prep"], None) is None
    assert len(agent.queue) == 2 and agent.cursor_stats == {"prep_item_flush": 1}
    assert "you carry no cobblestone any more" in agent.notes[0]
    assert "Nothing was done with another item in its place" in agent.notes[0]


def test_the_pillar_note_names_what_left_the_inventory():
    def run(before, after, item="cobblestone"):
        notes: list[str] = []
        agent = SimpleNamespace(
            _cur_pos={"x": 0.5, "y": 70.0, "z": 0.5, "pitch": 90.0, "yaw": 0.0}, _gui_open=False,
            _cur_info=_info(before), cursor_stats={}, memory=SimpleNamespace(add_note=notes.append))
        pl = {"item": item, "target": 4, "placed": 0, "phase": "look", "t": 0, "tries": 0,
              "y_jump": None, "budget": 126, "used": 0}
        MW._pillar_tick(agent, pl, lambda **kw: kw)          # the first tick takes the baseline
        pl.update(placed=3, tries=1, t=16)
        agent._cur_info = _info(after)
        assert MW._pillar_tick(agent, pl, lambda **kw: kw) is None
        return notes[-1], agent.cursor_stats

    note, stats = run(AFTER_PLACE_AT, {**TOOLS, 5: ("cobblestone", 52), 20: ("obsidian", 3)})
    assert "3 of 4 cobblestone placed" in note and "NOT cobblestone" not in note
    assert "pillar_wrong_item" not in stats
    # the recorded case: obsidian in the selected slot
    note, stats = run(AT_PARSE, {**TOOLS, 20: ("cobblestone", 55)})
    assert "NOT cobblestone: the inventory lost 3 obsidian" in note
    assert stats["pillar_wrong_item"] == 1
