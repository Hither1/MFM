"""`--human-play` (mcu_worldmodel/human.py): the memory mechanism and the state text stay,
no built-in skills beyond the GUI cursor primitives and watch, no advice, no reflexes,
the model writes its own scripts. User 2026-09-07 13:0x-13:3x."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_feedback_only_keeps_the_fact_and_drops_the_advice():
    from mcu_worldmodel.human import feedback_only

    assert feedback_only("took 4 damage -- health 15/20 at (-2957, 10, -5511). The plan was "
                         "interrupted; find the danger (a monster behind you?) before continuing.") == \
        "took 4 damage -- health 15/20 at (-2957, 10, -5511)."
    assert feedback_only("YOU DIED at (-3005, 9, -5581) and respawned at (-3010, 71, -5572). "
                         "Everything you carried dropped at the death point.") == \
        "YOU DIED at (-3005, 9, -5581) and respawned at (-3010, 71, -5572)."
    assert feedback_only("watch(until=inventory): not met in 10 tick(s); the game's numbers did "
                         "not change that way.") == \
        "watch(until=inventory): not met in 10 tick(s); the game's numbers did not change that way."
    assert feedback_only("") == ""


def test_human_atoms_are_the_cursor_and_watch():
    from mcu_worldmodel import procedures as P

    assert set(P.HUMAN_ATOMS) == {"open_inventory", "close_inventory", "cursor_to_slot",
                                  "cursor_to_cell", "gui_click", "gui_right_click", "watch"}
    P.set_visible(P.HUMAN_ATOMS)
    try:
        acts, note = P.expand("craft", item="stone_pickaxe")
        assert acts == [] and "not a built-in in this run" in note and "mine/procedures/" in note
        assert P.index().count("\n") + 1 == 7 and "`watch(" in P.index()
    finally:
        P.set_visible(None)


CHOP = '''"""chop: hold attack for n ticks, then step forward."""
import json, sys
PARAMS = {"n": "ticks (default 20)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
state = json.load(sys.stdin)
assert "pos" in state and "health" in state
print(json.dumps({"actions": [{"action": {"attack": 1}, "repeat": int(args.get("n", 20))},
                              {"action": {"forward": 1}, "repeat": 2}]}))
'''


def test_chassis_human_play(tmp_path: Path):
    from test_pins_chassis import drive_chassis
    from mcu_worldmodel import procedures as P

    ws = tmp_path / "ws"
    (ws / "mine" / "procedures").mkdir(parents=True)
    (ws / "mine" / "procedures" / "chop.py").write_text(CHOP)
    same = {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]}, "message": "[PLAN]\nsame"}
    script = [{"actions": {"actions": [{"procedure": "chop", "args": {"n": 8}},
                                       {"procedure": "craft", "args": {"item": "stick"}},
                                       {"procedure": "go_to", "args": {"x": 1.0, "z": 1.0}},
                                       {"action": {"camera": [5, 10]}, "repeat": 2}]},
               "message": "[PLAN]\nchop"}] + [same] * 24
    try:
        agent, _ = drive_chassis(tmp_path, "mfm", human_play=True, script=script)
        assert agent.human_play and agent.own and agent.reflexes is False
        root = agent.memory.root
        contract = (root / "AGENTS.md").read_text()
        assert contract.startswith("You are playing Minecraft the way a person does")
        assert "**Invent your skills.**" in contract and "mine/procedures/<name>.py" in contract
        assert "**Actions.**" in contract and "hotbar.1 .. hotbar.9" in contract
        assert "`cursor_to_slot(" in contract and "`watch(" in contract
        assert "`craft(" not in contract and "`go_to(" not in contract and "chop_tree" not in contract
        assert "**Your own files and procedures.**" in contract
        assert "**References.**" not in contract and not (root / "references").exists()
        assert "OBSERVED vs EXPECTED" in contract and "./actions.json" in contract
        log = (root / "logs.txt").read_text()
        assert "[ACTION] chop(n=8)" in log and "[STATE]" in log and "[INV]" in log or "[STATE]" in log
        assert "'craft' is not a built-in in this run" in log
        assert "'go_to' is not a built-in in this run" in log
        assert "governor:" not in log                       # 24 identical plans, no refusal, no nudge
        assert "stone sword" not in log.lower() or "craft it now" not in log
        prompts = agent.codex.prompts
        assert prompts and all("[OWN] your own procedures" in p and "[STATE]" in p for p in prompts)
        assert not any("2x2 sheet" in p for p in prompts)
        # a note reaches the log as its first sentence only
        agent.memory.add_note("took 4 damage -- health 15/20 at (1, 2, 3). The plan was interrupted; find the danger.")
        assert agent.memory._pending_notes[-1] == "took 4 damage -- health 15/20 at (1, 2, 3)."
        r = agent.report()
        assert r["human_play"] is True and r["own"]["calls"] == {"chop": 1}
    finally:
        P.set_visible(None)


def test_human_play_needs_mfm(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger

    with pytest.raises(ValueError):
        WorldModelAgent(workspace=tmp_path / "ws", task_text="t", ledger=MilestoneLedger([], "t"),
                        induction_every=10, step_cap=50, memory_mode="logbook", human_play=True)
