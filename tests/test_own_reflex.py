"""`--own-reflexes` (mcu_worldmodel/own.py, 2026-09-07): mine/reflexes/<name>.py scripts run
every REFLEX_EVERY ticks on the live state and may stop the plan, note, and queue a short
plan; a script that keeps failing is switched off until edited; the [OWN] block lists them;
the contract names what to write first."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

STATE = {"step": 40, "max_steps": 100,
         "pos": {"x": 1.0, "y": 64.0, "z": 1.0, "pitch": 0.0, "yaw": 0.0},
         "health": 12.0, "food": 20.0, "inventory": {}, "hotbar": [], "gui_open": False,
         "dimension": "the Overworld", "lava_frac": 0.3, "health_prev": 16.0,
         "pos_prev": {"x": 0.0, "y": 64.0, "z": 1.0, "pitch": 0.0, "yaw": 0.0},
         "entry": "go_to", "queue_len": 12, "runner_reflex": None}

LAVA = '''"""lava_walk: stop a walk when lava fills 5%+ of the lower view."""
import json, sys
s = json.load(sys.stdin)
if s["lava_frac"] >= 0.05 and s["entry"] in ("go_to", "raw", "mine_forward"):
    print(json.dumps({"stop": True, "note": "lava %.0f%% in view during %s" % (100 * s["lava_frac"], s["entry"]),
                      "actions": [{"action": {"back": 1}, "repeat": 4}]}))
'''

QUIET = '''"""quiet: never fires."""
import json, sys
s = json.load(sys.stdin)
print("{}")
'''


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "mine" / "reflexes").mkdir(parents=True)
    return ws


def test_scan_run_and_block(tmp_path: Path):
    from mcu_worldmodel import own

    ws = _ws(tmp_path)
    d = ws / "mine" / "reflexes"
    (d / "lava_walk.py").write_text(LAVA)
    (d / "quiet.py").write_text(QUIET)
    (d / "bad.py").write_text("def (:\n")
    (d / "_x.py").write_text("X = 1\n")
    rx = own.scan_reflexes(ws)
    assert set(rx) == {"lava_walk", "quiet", "bad"}
    assert rx["lava_walk"].doc.startswith("lava_walk: stop a walk") and rx["lava_walk"].mtime > 0
    assert "does not parse" in rx["bad"].error
    res, err = own.run_reflex(rx["lava_walk"], ws, STATE)
    assert err is None and res["stop"] is True and "lava 30% in view during go_to" in res["note"]
    assert res["actions"] == [{"action": {"back": 1}, "repeat": 4}]
    assert own.run_reflex(rx["lava_walk"], ws, dict(STATE, lava_frac=0.0)) == (None, None)
    assert own.run_reflex(rx["quiet"], ws, STATE) == (None, None)
    assert own.run_reflex(rx["bad"], ws, STATE)[1].startswith("does not parse")
    (d / "off.py").write_text('print(\'{"fire": false}\')\n')
    (d / "nokeys.py").write_text('print(\'{"x": 1}\')\n')
    (d / "notjson.py").write_text("print('hello')\n")
    (d / "alist.py").write_text("print('[1]')\n")
    (d / "boom.py").write_text("import sys\nprint('no state', file=sys.stderr)\nraise SystemExit(3)\n")
    (d / "slow.py").write_text("import time\ntime.sleep(5)\n")
    rx = own.scan_reflexes(ws)
    assert own.run_reflex(rx["off"], ws, STATE) == (None, None)
    assert "needs `stop`, `note` or `actions`" in own.run_reflex(rx["nokeys"], ws, STATE)[1]
    assert "not JSON" in own.run_reflex(rx["notjson"], ws, STATE)[1]
    assert "JSON object" in own.run_reflex(rx["alist"], ws, STATE)[1]
    assert own.run_reflex(rx["boom"], ws, STATE)[1] == "exit code 3: no state"
    assert "timed out" in own.run_reflex(rx["slow"], ws, STATE, timeout=0.5)[1]
    block = own.reflex_block(rx, {"lava_walk": 2}, {"quiet": "exit code 1: x"})
    assert block.startswith("[OWN] your own reflexes")
    assert "- `lava_walk` -- lava_walk: stop a walk when lava fills 5%+ of the lower view. [fired 2x]" in block
    assert "- `quiet` -- switched OFF (exit code 1: x)" in block
    assert "- `bad` -- NOT running: does not parse" in block
    assert own.reflex_block({}, {}, {}) == ""


def test_contract_carries_the_reflex_and_digest_notes():
    from mcu_worldmodel import own, prompts
    from mcu_worldmodel.previous import MFM_DIGEST_NOTE

    assert "worth writing FIRST" in own.MFM_REFLEX_NOTE
    assert "mine/reflexes/<name>.py" in own.MFM_REFLEX_NOTE
    c = prompts._mfm_contract(own=True, own_reflexes=True, previous=True)
    assert "**Your own reflexes.**" in c and "**Your own files and procedures.**" in c
    assert MFM_DIGEST_NOTE.strip() in c and "mine/digest.md" in c
    assert c.index("**Your own files and procedures.**") < c.index("**Your own reflexes.**")
    c2 = prompts._mfm_contract(own=True, own_reflexes=False, previous=False)
    # (2026-09-09: the working-memory note names mine/digest.md for every own arm; the carried-lives
    # digest paragraph itself still appears only with previous lives)
    assert "**Your own reflexes.**" not in c2 and MFM_DIGEST_NOTE.strip() not in c2
    c3 = prompts._mfm_contract(own=False, own_reflexes=True, previous=True)
    assert "**Your own reflexes.**" not in c3 and "mine/digest.md" not in c3


def test_chassis_reflex_fires_and_a_broken_one_is_switched_off(tmp_path: Path):
    from test_pins_chassis import drive_chassis

    ws = tmp_path / "ws"
    d = ws / "mine" / "reflexes"
    d.mkdir(parents=True)
    # fires once the plan has run a few ticks: stops it, notes, and watches 6 ticks
    (d / "halt.py").write_text(
        '"""halt: stop the walk after step 12."""\n'
        'import json, sys\ns = json.load(sys.stdin)\n'
        'if 12 <= s["step"] < 20 and s["entry"] == "raw" and s["queue_len"] > 0:\n'
        '    print(json.dumps({"stop": True, "note": "step %d, %s running, hp %s -> %s" % '
        '(s["step"], s["entry"], s["health_prev"], s["health"]),'
        ' "actions": [{"procedure": "watch", "args": {"n": 6}}]}))\n')
    (d / "boom.py").write_text("raise SystemExit(2)\n")
    script = [{"actions": {"actions": [{"action": {"forward": 1}, "repeat": 40}]},
               "message": "[PLAN]\nwalk"}] + [
        {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
         "message": f"[PLAN]\nchop {i}"} for i in range(20)]
    agent, actions = drive_chassis(tmp_path, "mfm", thin=True, own=True, own_reflexes=True,
                                   script=script, steps=60)
    assert agent.own_reflexes is True
    log = (ws / "logs.txt").read_text()
    assert "[REFLEX halt] step 12, raw running" in log
    assert "the runner dropped the rest of your plan" in log and "running the reflex's own actions" in log
    assert log.index("[REFLEX halt]") < log.index("watch(until=none): waited 6 tick(s)")
    assert "[REFLEX boom] switched OFF after 3 failures in a row (exit code 2 (nothing on stderr))" in log
    assert agent.cursor_stats["own_reflex_fires"] >= 1
    assert agent.cursor_stats["own_reflex_failures"] == 3           # off after the third
    assert "boom" in agent._own_reflex_off and "halt" not in agent._own_reflex_off
    # the walk was cut: fewer than 40 forward ticks before the first non-forward action
    fwd = 0
    for a in actions[1:]:
        if a.get("forward"):
            fwd += 1
        else:
            break
    assert 0 < fwd < 40
    prompts = agent.codex.prompts
    assert any("[OWN] your own reflexes" in p and "`halt` -- halt: stop the walk" in p for p in prompts)
    assert any("`boom` -- switched OFF" in p for p in prompts)
    contract = (ws / "AGENTS.md").read_text()
    assert "**Your own reflexes.**" in contract
    r = agent.report()
    assert r["own"]["reflexes"] == 2 and r["own"]["reflex_fires"] == {"halt": 1}
    # editing the broken file switches it back on
    time.sleep(0.02)
    (d / "boom.py").write_text("print('{}')\n")
    os.utime(d / "boom.py", None)
    agent._scan_own_reflexes()
    assert "boom" not in agent._own_reflex_off
