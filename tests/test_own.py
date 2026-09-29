"""`--atoms` (procedures.ATOMS is the visible set) and `--own` (mine/ persists,
mine/procedures/*.py are procedures run in a subprocess: mcu_worldmodel/own.py).
tasks/mfm-three-layer.self-harness, 2026-09-07."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CHOP = '''"""chop: aim at the block ahead and mine it, then step up to the drop."""
import json, sys
PARAMS = {"n": "ticks to mine (default 40)"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
state = json.load(sys.stdin)
n = int(args.get("n", 40))
assert state["pos"] is None or "x" in state["pos"]
assert "inventory" in state and "health" in state
print(json.dumps({"actions": [{"procedure": "mine_ahead", "args": {"n": n}},
                              {"action": {"forward": 1}, "repeat": 3}]}))
'''

STATE = {"step": 5, "max_steps": 100,
         "pos": {"x": 1.0, "y": 64.0, "z": 1.0, "pitch": 0.0, "yaw": 0.0},
         "health": 20.0, "food": 20.0, "inventory": {}, "hotbar": [], "gui_open": False,
         "dimension": None}


@pytest.fixture(autouse=True)
def _visible_reset():
    from mcu_worldmodel import procedures as P
    yield
    P.set_visible(None)


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "mine" / "procedures").mkdir(parents=True)
    return ws


def test_atoms_is_the_visible_set():
    from mcu_worldmodel import procedures as P

    assert all(n in P.REGISTRY for n in P.ATOMS)
    P.set_visible(P.ATOMS)
    idx = P.index()
    assert idx.count("\n") + 1 == len(P.ATOMS)
    assert "`craft(" in idx and "`go_to(" in idx and "`watch(" in idx
    assert "chop_tree" not in idx and "mine_obsidian" not in P.reference()
    acts, note = P.expand("chop_tree", n=10)
    assert acts == [] and "not in this run's procedure set" in note and "mine/procedures/" in note
    acts, note = P.expand("go_to", x=1.0, z=1.0)
    assert acts and not note
    acts, note = P.expand("no_such_thing")
    assert acts == [] and "unknown procedure" in note
    P.set_visible(None)
    assert "chop_tree" in P.index()


def test_scan_and_run_own_scripts(tmp_path: Path):
    from mcu_worldmodel import own
    from mcu_worldmodel import procedures as P

    ws = _ws(tmp_path)
    d = ws / "mine" / "procedures"
    (d / "chop.py").write_text(CHOP)
    (d / "go_to.py").write_text(CHOP)                 # shadows a built-in
    (d / "bad.py").write_text("def (:\n")             # does not parse
    (d / "_helper.py").write_text("X = 1\n")          # private, not a procedure
    procs = own.scan(ws, set(P.REGISTRY))
    assert set(procs) == {"chop", "go_to", "bad"}
    assert procs["chop"].doc.startswith("chop: aim")
    assert procs["chop"].params == {"n": "ticks to mine (default 40)"}
    assert "built-in" in procs["go_to"].error and "does not parse" in procs["bad"].error
    out, err = own.run(procs["chop"], ws, STATE, {"n": 12})
    assert err is None and json.loads(out)["actions"][0]["args"]["n"] == 12
    assert own.run(procs["bad"], ws, STATE, {})[1].startswith("does not parse")
    (d / "boom.py").write_text("import sys\nprint('x', file=sys.stderr)\nraise SystemExit(3)\n")
    (d / "slow.py").write_text("import time\ntime.sleep(5)\n")
    (d / "quiet.py").write_text("pass\n")
    procs = own.scan(ws, set(P.REGISTRY))
    assert own.run(procs["boom"], ws, STATE, {})[1] == "exit code 3: x"
    assert "timed out" in own.run(procs["slow"], ws, STATE, {}, timeout=0.5)[1]
    assert "printed nothing" in own.run(procs["quiet"], ws, STATE, {})[1]
    block = own.index_block(procs, {"chop": 2})
    assert block.startswith("[OWN]")
    assert "- `chop(n=<ticks to mine (default 40)>)` -- chop: aim" in block
    assert "[called 2x]" in block and "NOT callable" in block
    assert own.index_block({}, {}) == ""


def test_parse_actions_expands_own_procedures(tmp_path: Path):
    from mcu_worldmodel import own
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.actions import parse_actions

    ws = _ws(tmp_path)
    d = ws / "mine" / "procedures"
    (d / "chop.py").write_text(CHOP)
    (d / "twice.py").write_text(
        'import json\nprint(json.dumps({"actions": [{"procedure": "chop", "args": {}}, '
        '{"action": {"jump": 1}, "repeat": 2}]}))\n')
    (d / "boom.py").write_text("raise SystemExit(2)\n")
    procs = own.scan(ws, set(P.REGISTRY))
    calls: list[str] = []

    def expand(name, args):
        calls.append(name)
        return own.run(procs[name], ws, STATE, args)
    text = json.dumps({"actions": [{"procedure": "chop", "args": {"n": 12}},
                                   {"procedure": "boom"},
                                   {"procedure": "twice"},
                                   {"procedure": "nope"},
                                   {"action": {"attack": 1}, "repeat": 2}]})
    plan = parse_actions(text, step_cap=400, own_expand=expand, own_names=set(procs))
    assert calls == ["chop", "boom", "twice"]
    names = [k["procedure"] for k in plan.entries if "procedure" in k]
    assert names == ["chop", "twice"]
    chop = plan.entries[0]
    assert chop["own"] is True and chop["args"] == {"n": 12}
    assert chop["items"] >= 4 and chop["steps"] >= 15            # mine_ahead + 3 raw ticks
    twice = plan.entries[1]
    assert twice["items"] == 2 and twice["steps"] == 2            # the jumps; the nested own call skipped
    assert len(plan.steps) == chop["items"] + 2 + 2
    assert any("boom (mine/procedures/boom.py) FAILED" in n and "exit code 2 (nothing on stderr)" in n for n in plan.notes)
    assert any(n.startswith("twice: chop: an own procedure cannot call another") for n in plan.notes)
    assert any("unknown procedure 'nope'" in n for n in plan.notes)
    # without the hook the names are known but refused
    plan2 = parse_actions(text, step_cap=400, own_names=set(procs))
    assert not plan2.entries[:1] or "procedure" not in plan2.entries[0] or plan2.entries[0]["procedure"] != "chop"
    assert any("own procedures are not enabled" in n for n in plan2.notes)
    # the step cap bounds the script's plan like any other
    plan3 = parse_actions(json.dumps({"actions": [{"procedure": "chop", "args": {"n": 300}}]}),
                          step_cap=20, own_expand=expand, own_names=set(procs))
    assert sum(max(0, int(s.get("_cost", 1))) for s in plan3.steps) <= 20


def test_sweep_keeps_mine_only_with_own(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory

    mem = MultimodalMemory(tmp_path / "a", episodes=True, own=True)
    (mem.root / "mine" / "procedures").mkdir(parents=True)
    (mem.root / "mine" / "notes.md").write_text("kept")
    (mem.root / "scratch.md").write_text("swept")
    removed = mem.sweep_foreign()
    assert "scratch.md" in removed and "mine" not in removed
    assert (mem.root / "mine" / "notes.md").exists()
    mem2 = MultimodalMemory(tmp_path / "b", episodes=True)
    (mem2.root / "mine").mkdir()
    (mem2.root / "mine" / "x").write_text("x")
    assert "mine" in mem2.sweep_foreign()


def test_carry_links_mine(tmp_path: Path):
    from test_previous import make_life
    from mcu_worldmodel.previous import PreviousLives

    life = make_life(tmp_path, "gen1")
    (life / "mine" / "procedures").mkdir(parents=True)
    (life / "mine" / "procedures" / "chop.py").write_text(CHOP)
    (life / "mine" / "notes.md").write_text("n")
    pl = PreviousLives(tmp_path / "gen2")
    pl.seed([life])
    assert (tmp_path / "gen2" / "previous" / "life_1" / "mine" / "procedures" / "chop.py").read_text() == CHOP
    assert (tmp_path / "gen2" / "previous" / "life_1" / "mine" / "notes.md").read_text() == "n"


def test_chassis_thin_atoms_own(tmp_path: Path):
    from test_pins_chassis import drive_chassis

    ws = tmp_path / "ws"
    (ws / "mine" / "procedures").mkdir(parents=True)
    (ws / "mine" / "procedures" / "chop.py").write_text(CHOP)
    script = [
        {"actions": {"actions": [{"procedure": "chop", "args": {"n": 6}}]},
         "message": "[PLAN]\nchop"},
        {"actions": {"actions": [{"procedure": "chop_tree", "args": {"n": 6}},
                                 {"action": {"attack": 1}, "repeat": 2}]},
         "message": "[PLAN]\ntree"},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
          "message": f"[PLAN]\nchop {i}"} for i in range(20)]
    agent, _ = drive_chassis(tmp_path, "mfm", thin=True, own=True, atoms=True, script=script)
    root = agent.memory.root
    contract = (root / "AGENTS.md").read_text()
    head = contract.split("**References.**")[0]
    assert "**Your own files and procedures.**" in head and "ATOMS above" in head
    assert "`craft(" in head and "chop_tree" not in head
    assert "outside `mine/`" in contract
    assert "chop_tree" not in (root / "references" / "procedures.md").read_text()
    log = (root / "logs.txt").read_text()
    assert "[ACTION] chop(n=6)" in log
    assert "'chop_tree' is not in this run's procedure set" in log
    assert (root / "mine" / "procedures" / "chop.py").exists()        # survived the sweeps
    prompts = agent.codex.prompts
    assert any("[OWN] your own procedures" in p and "`chop(n=" in p for p in prompts)
    assert any("[called 1x]" in p for p in prompts)
    r = agent.report()
    assert r["atoms"] is True and r["own"] == {"procedures": 1, "calls": {"chop": 1}}
    assert agent.cursor_stats.get("own_calls") == 1 and not agent.cursor_stats.get("own_failures")


def test_own_needs_mfm(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger

    with pytest.raises(ValueError):
        WorldModelAgent(workspace=tmp_path / "ws", task_text="t", ledger=MilestoneLedger([], "t"),
                        step_cap=50, memory_mode="logbook", own=True)
