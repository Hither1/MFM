"""`--visual-only` (mcu_worldmodel/visual.py): the model is served the frame alone --
no state/inventory/map text, no retrieval block, no event sheet, coordinate-free atoms,
notes scrubbed of coordinates, no positions on disk for it to read. User ask 2026-09-07."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_scrub_removes_coordinates_and_headings():
    from mcu_worldmodel.visual import scrub

    assert scrub("LAVA AHEAD: 27% of the lower view is lava at (-2988, 12, -5558) facing yaw -810. "
                 "Do not walk into it.") == \
        "LAVA AHEAD: 27% of the lower view is lava at (a spot near you). Do not walk into it."
    assert scrub("YOU DIED at (-3005, 9, -5581) and respawned at (-3010, 71, -5572).") == \
        "YOU DIED at (a spot near you) and respawned at (a spot near you)."
    assert scrub("go_to (-2989.0, -5558.5) stalled at (-2989.3, -5556.4)") == \
        "go_to (a spot) stalled at (a spot)"
    assert scrub("placed at x=-2983, y=64, z=-5668 -- pos=(1.0, 2.0, 3.0) heading 90") == \
        "placed at a spot near you --"
    # small numbers that are not coordinates stay (a GUI cell, a count)
    assert scrub("cursor at cell (1, 2); 3 of (4) items") == "cursor at cell (1, 2); 3 of (4) items"


def test_visual_atoms_take_no_coordinate():
    from mcu_worldmodel import procedures as P

    assert set(P.VISUAL_ATOMS) == set(P.ATOMS) - {"look_at", "look_abs", "place_at", "use_at", "go_to"}
    assert "look" in P.VISUAL_ATOMS and "mine_ahead" in P.VISUAL_ATOMS and "watch" in P.VISUAL_ATOMS


def test_chassis_visual_only(tmp_path: Path):
    from test_pins_chassis import drive_chassis
    from mcu_worldmodel import procedures as P

    script = [{"actions": {"actions": [{"procedure": "look", "args": {"pitch": 10, "yaw": 0}},
                                       {"procedure": "go_to", "args": {"x": 1.0, "z": 1.0}},
                                       {"action": {"forward": 1}, "repeat": 4}]},
               "message": "[PLAN]\nlook"}] + \
             [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
               "message": f"[PLAN]\nchop {i}"} for i in range(20)]
    try:
        agent, _ = drive_chassis(tmp_path, "mfm", thin=True, visual_only=True, script=script)
        root = agent.memory.root
        contract = (root / "AGENTS.md").read_text()
        head = contract.split("**References.**")[0]
        assert "**Visual input only.**" in head and "VISUAL ATOMS above" in head
        assert "`look(" in head and "`mine_ahead(" in head
        assert "`go_to(" not in head and "`look_abs(" not in head and "`place_at(" not in head
        assert "go_to" not in (root / "references" / "procedures.md").read_text()
        log = (root / "logs.txt").read_text()
        assert "[ACTION]" in log and "[STATE]" not in log and "[INV]" not in log
        assert "[GUI]" not in log and "[CURSOR]" not in log
        assert "'go_to' is not in this run's procedure set" in log
        assert not (root / "grid.jsonl").exists()
        prompts = agent.codex.prompts
        assert prompts and all("[STATE]" not in p and "Inventory (" not in p and "Hotbar:" not in p
                               and "[MAP]" not in p and "[RECALL]" not in p and "moved " not in p
                               for p in prompts)
        assert all("[VIEW] the current frame is attached" in p and "Nothing is shown unasked" in p
                   for p in prompts)
        # a harness note loses its coordinates before it reaches the log or the prompt
        agent.memory.add_note("LAVA AHEAD: 27% at (-2988, 12, -5558) facing yaw -810.")
        assert agent.memory._pending_notes[-1] == "LAVA AHEAD: 27% at (a spot near you)."
        # the episodes carry no position, inventory or vitals
        states = list((root / "episodes").glob("ep_*/state/state.json"))
        assert states
        for s in states:
            d = json.loads(s.read_text())
            assert set(d) <= {"step", "gui_open", "goals", "verified"}
        rows = [json.loads(l) for l in (root / "index.jsonl").read_text().splitlines() if l.strip()]
        assert rows and all(r.get("x") is None and r.get("z") is None for r in rows)
        r = agent.report()
        assert r["visual_only"] is True and r.get("atoms") is None
    finally:
        P.set_visible(None)


def test_visual_only_needs_mfm(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger

    with pytest.raises(ValueError):
        WorldModelAgent(workspace=tmp_path / "ws", task_text="t", ledger=MilestoneLedger([], "t"),
                        induction_every=10, step_cap=50, memory_mode="logbook", visual_only=True)
