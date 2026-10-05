"""`--own-live`: the model's own scripts see the view while its plan runs.

    mine/procedures/<name>.py with `LOOP = True`   a closed loop: run when its entry starts
                                                   and again each time what it returned has
                                                   run, on that tick's state and frame
    mine/reflexes/<name>.py                        gets the same frame on its stdin

Off, the shipped arm is byte for byte what it was (test_release_pins): a `LOOP = True`
line means nothing, no frame is written, the contract says nothing of it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_pins_chassis import _pov, drive_chassis
from test_release_pins import _arm

#: A loop that walks three ticks a call, four calls, and writes down what it was given.
FOLLOW = '''"""follow: three steps forward a call, and a record of every call."""
import hashlib, json, os, sys
LOOP = True
PARAMS = {"ticks": "budget", "calls": "calls before it says it is done"}
args = json.loads(sys.argv[sys.argv.index("--args") + 1]) if "--args" in sys.argv else {}
s = json.load(sys.stdin)
frame = s.get("frame")
row = {"step": s["step"], "call": s["call"], "ticks": s["ticks"], "budget": s["budget"],
       "memo": s["memo"], "x": s["pos"]["x"], "health_start": s["health_start"],
       "frame": os.path.basename(frame) if frame else None,
       "sha": hashlib.sha1(open(frame, "rb").read()).hexdigest() if frame else None,
       "keys": sorted(s)}
with open("mine/follow_calls.jsonl", "a") as f:
    f.write(json.dumps(row) + "\\n")
n = int(s["memo"].get("n", 0)) + 1
print(json.dumps({"actions": [{"action": {"forward": 1}, "repeat": 3}],
                  "again": n < int(args.get("calls", 4)), "memo": {"n": n},
                  "note": "call %d at step %d" % (s["call"], s["step"])}))
'''


def _script(entry: dict) -> list[dict]:
    # The chassis under test verifies a milestone at step 8, and a verified milestone
    # drops the plan (a loop with it): the first turn idles past it.
    return ([{"actions": {"actions": [{"action": {"sneak": 1}, "repeat": 12}]},
              "message": "[PLAN]\nwait"},
             {"actions": {"actions": [entry, {"action": {"jump": 1}, "repeat": 2}]},
              "message": "[PLAN]\nrun the loop, then jump twice"}]
            + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
                "message": "[PLAN]\nchop"}] * 30)


def _life(tmp: Path, src: str, entry: dict, name: str = "follow", steps: int = 60, **kw):
    d = tmp / "ws" / "mine" / "procedures"
    d.mkdir(parents=True)
    (d / f"{name}.py").write_text(src)
    return drive_chassis(tmp, "mfm", steps=steps, script=_script(entry), **kw, **_arm("mfm"))


def _play(agent, step: int, health: float):
    """One more step of a life `drive_chassis` started: an action, then the observation."""
    import numpy as np
    from mcu_worldmodel.testing import fake_info
    info = fake_info(inventory={"oak_log": 2}, mine_block={"oak_log": 1})
    info["location_stats"].update(xpos=np.array(1.0 + 0.3 * step), ypos=np.array(64.0),
                                  zpos=np.array(0.0))
    info["health"] = np.array(health)
    info["pov"] = _pov(step)
    act = agent.next_action(info)
    agent.observe(info, step)
    return act


def _notes(agent) -> str:
    return "\n".join(agent.memory._pending_notes) + (agent.memory.root / "logs.txt").read_text()


def _rows(agent) -> list[dict]:
    p = agent.memory.root / "mine" / "follow_calls.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def _contract(agent) -> str:
    ws = agent.memory.root
    return next(ws / n for n in ("CLAUDE.md", "AGENTS.md") if (ws / n).exists()).read_text()


def test_a_loop_is_run_during_the_plan_on_the_frame_of_each_call(tmp_path: Path):
    agent, actions = _life(tmp_path, FOLLOW, {"procedure": "follow", "args": {"ticks": 40}},
                           own_live=True)
    rows = _rows(agent)
    assert [r["call"] for r in rows] == [0, 1, 2, 3]
    # each call comes when the three ticks the last one returned have run
    assert [r["ticks"] for r in rows] == [0, 3, 6, 9]
    assert [r["step"] - rows[0]["step"] for r in rows] == [0, 3, 6, 9]
    assert [r["budget"] for r in rows] == [40, 37, 34, 31]
    # its memory between calls is what it returned under `memo`
    assert [r["memo"] for r in rows] == [{}, {"n": 1}, {"n": 2}, {"n": 3}]
    # the state is the state of THAT tick, and the frame the frame of that tick
    assert len({r["x"] for r in rows}) == 4
    assert all(r["frame"] == "live.png" for r in rows) and len({r["sha"] for r in rows}) == 4
    assert {"frame", "lava_frac", "fire_frac", "call", "ticks", "budget", "memo",
            "health_start"} <= set(rows[0]["keys"])
    # what ran: twelve ticks of the loop's walking, then the plan's own next entry
    first = next(i for i, a in enumerate(actions) if a.get("forward"))
    assert all(a.get("forward") for a in actions[first:first + 12])
    assert all(a.get("jump") for a in actions[first + 12:first + 14])
    log = (agent.memory.root / "logs.txt").read_text()
    assert "[LOOP follow] call 0 at step" in log
    assert "[LOOP follow] ended: it was done (4 call(s), 12 of 40 ticks)." in log
    assert log.index("[ACTION] follow(") < log.index("[LOOP follow] ended") < log.index('{"jump":1}')
    rep = agent.report()
    assert rep["own_live"] is True
    assert rep["own_loops"] == {"follow": {"entries": 1, "calls": 4, "ticks": 12}}
    assert rep["own"]["calls"] == {"follow": 1}
    # the frame is beside the workspace, not in it: nothing of it is listed or carried
    assert (agent.memory.attach_dir / "live.png").exists()
    assert not list(agent.memory.root.rglob("live.png"))
    # the [OWN] block of the next turn names it as what it is
    assert any("`follow(" in p and "closed loop; called 1x" in p for p in agent.codex.prompts)


def test_a_loop_ends_when_its_budget_is_spent(tmp_path: Path):
    agent, actions = _life(tmp_path, FOLLOW,
                           {"procedure": "follow", "args": {"ticks": 10, "calls": 99}},
                           own_live=True)
    rows = _rows(agent)
    assert [r["ticks"] for r in rows] == [0, 3, 6, 9]
    assert rows[-1]["budget"] == 1
    first = next(i for i, a in enumerate(actions) if a.get("forward"))
    # the last call's three ticks are cut to the one tick the budget has left
    assert sum(1 for a in actions[first:first + 12] if a.get("forward")) == 10
    log = (agent.memory.root / "logs.txt").read_text()
    assert "[LOOP follow] ended: its budget is spent (4 call(s), 10 of 10 ticks)." in log
    assert agent.report()["own_loops"]["follow"] == {"entries": 1, "calls": 4, "ticks": 10}


def test_a_budget_over_the_plans_step_cap_is_shrunk_and_said(tmp_path: Path):
    agent, _ = _life(tmp_path, FOLLOW, {"procedure": "follow", "args": {"calls": 2}},
                     own_live=True)
    log = (agent.memory.root / "logs.txt").read_text()
    # the chassis under test has a 50-tick plan; the default budget is 200
    assert "follow: its loop shrunk to fit the step cap: 200 -> 50 ticks" in log
    assert _rows(agent)[0]["budget"] == 50


def test_a_failing_call_ends_the_loop_and_the_plan_goes_on(tmp_path: Path):
    src = FOLLOW.replace('n = int(s["memo"].get("n", 0)) + 1',
                         'n = int(s["memo"].get("n", 0)) + 1\n'
                         'if s["call"] == 1:\n    raise SystemExit("lost the target")')
    agent, actions = _life(tmp_path, src, {"procedure": "follow", "args": {"ticks": 40}},
                           own_live=True)
    assert [r["call"] for r in _rows(agent)] == [0, 1]
    log = (agent.memory.root / "logs.txt").read_text()
    assert "[LOOP follow] ended: call 1 FAILED, nothing ran: exit code 1: lost the target" in log
    first = next(i for i, a in enumerate(actions) if a.get("forward"))
    assert all(a.get("jump") for a in actions[first + 3:first + 5])


def test_a_loop_cannot_call_another_own_procedure(tmp_path: Path):
    src = FOLLOW.replace('[{"action": {"forward": 1}, "repeat": 3}]',
                         '[{"procedure": "follow", "args": {}}, {"action": {"forward": 1}, "repeat": 3}]')
    agent, _ = _life(tmp_path, src, {"procedure": "follow", "args": {"ticks": 40, "calls": 2}},
                     own_live=True)
    log = (agent.memory.root / "logs.txt").read_text()
    assert "[LOOP follow] follow: an own procedure cannot call another own procedure" in log
    assert [r["call"] for r in _rows(agent)] == [0, 1]


def test_without_the_flag_the_same_script_is_an_ordinary_procedure(tmp_path: Path):
    agent, actions = _life(tmp_path, FOLLOW.replace('row = {', 's.setdefault("call", 0); '
                           's.setdefault("ticks", 0); s.setdefault("budget", 0); '
                           's.setdefault("memo", {}); s.setdefault("health_start", 0)\nrow = {'),
                           {"procedure": "follow", "args": {"ticks": 40}})
    rows = _rows(agent)
    # run once, at plan time, from the numbers of the turn: no frame, no second call
    assert len(rows) == 1 and rows[0]["frame"] is None and "lava_frac" not in rows[0]["keys"]
    first = next(i for i, a in enumerate(actions) if a.get("forward"))
    assert sum(1 for a in actions[first:first + 6] if a.get("forward")) == 3
    log = (agent.memory.root / "logs.txt").read_text()
    assert "[LOOP" not in log
    assert not (agent.memory.attach_dir / "live.png").exists()
    rep = agent.report()
    assert "own_live" not in rep and "own_loops" not in rep
    assert "Closed-loop" not in _contract(agent)
    assert "Closed-loop" not in (agent.memory.root / "references" / "own.md").read_text()
    assert not any("closed loop" in p for p in agent.codex.prompts)


def test_the_contract_says_what_a_loop_is_given_and_must_print(tmp_path: Path):
    from mcu_worldmodel import own
    agent, _ = _life(tmp_path, FOLLOW, {"procedure": "follow", "args": {"ticks": 40}},
                     own_live=True)
    contract = _contract(agent)
    assert contract.rstrip().endswith(own.LIVE_NOTE.rstrip())
    ref = (agent.memory.root / "references" / "own.md").read_text()
    assert own.loop_note((320, 180)) in ref and "320x180" in ref
    # the numbers the text states are the numbers the runner enforces
    assert f"at\n  most {own.LOOP_ENTRY_CAP} entries and {own.LOOP_CALL_TICKS} ticks per call" in ref
    assert f"default {own.LOOP_BUDGET}" in ref
    assert (f"{own.LOOP_COLD_TIMEOUT_S:.0f} s on the first call" in ref
            and f"{own.LOOP_TIMEOUT_S:.0f} s after" in ref and "`frame_size`" in ref)
    assert f"at most {own.LOOP_NOTES} per entry" in ref
    # nothing in it is a skill: no mob, no detector, no aim rule
    for word in ("blaze", "enderman", "dragon", "sword", "yellow", "attack"):
        assert word not in own.LIVE_NOTE.lower() and word not in own.loop_note((320, 180)).lower()


def test_a_reflex_gets_the_frame_too(tmp_path: Path):
    watch = ('"""watch: writes down what a reflex is given; never fires."""\n'
             'import json, os, sys\ns = json.load(sys.stdin)\n'
             'open("mine/reflex_keys.json", "w").write(json.dumps({"keys": sorted(s), '
             '"frame": s.get("frame"), "there": bool(s.get("frame")) and os.path.exists(s["frame"])}))\n')
    for name, kw in (("on", {"own_live": True}), ("off", {})):
        root = tmp_path / name
        d = root / "ws" / "mine" / "reflexes"
        d.mkdir(parents=True)
        (d / "watch.py").write_text(watch)
        agent, _ = drive_chassis(root, "mfm", steps=40, **kw, **_arm("mfm"))
        seen = json.loads((agent.memory.root / "mine" / "reflex_keys.json").read_text())
        if kw:
            assert seen["there"] and seen["frame"].endswith("attach/live.png")
        else:
            assert "frame" not in seen["keys"]


def test_the_live_view_needs_the_arm_that_writes_scripts(tmp_path: Path):
    with pytest.raises(ValueError, match="own_live"):
        drive_chassis(tmp_path, "mfm", own_live=True, **_arm("mfm-matched"))


# -- the fixes of 2026-10-05, after the night enderman chain (0 hits in 6,000 steps) -----

#: A loop that sneaks three ticks a call for as long as its budget lasts, and writes
#: down the health it was handed at every call.
HOLD = '''"""hold: three ticks of sneaking a call, for the whole budget; records health."""
import json, sys
LOOP = True
s = json.load(sys.stdin)
with open("mine/hold_calls.jsonl", "a") as f:
    f.write(json.dumps({"step": s["step"], "call": s["call"], "health": s["health"]}) + "\\n")
print(json.dumps({"actions": [{"action": {"sneak": 1}, "repeat": 3}], "again": True}))
'''


def _calls(agent, name: str) -> list[dict]:
    p = agent.memory.root / "mine" / f"{name}_calls.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def test_a_loop_entry_survives_a_hit_and_an_ordinary_entry_does_not(tmp_path: Path):
    # the loop: turn 1 idles 12 ticks, turn 2 starts the loop with a 90-tick budget
    agent, _ = _life(tmp_path / "loop", HOLD, {"procedure": "hold", "args": {"ticks": 90}},
                     name="hold", steps=16, own_live=True)
    for step in range(17, 41):
        _play(agent, step, health=20.0 if step < 24 else 14.0)   # a 6-point hit at step 24
    rows = _calls(agent, "hold")
    assert any(r["step"] >= 30 and r["health"] == 14.0 for r in rows), rows
    assert "interrupted" not in _notes(agent)
    # at critical health the stop still wins
    for step in range(41, 52):
        _play(agent, step, health=14.0 if step < 44 else 5.0)
    assert "CRITICAL" in _notes(agent)
    assert not any(r["step"] >= 48 for r in _calls(agent, "hold"))
    # the same hit drops an ordinary entry
    agent, _ = _life(tmp_path / "raw", HOLD, {"action": {"sneak": 1}, "repeat": 90},
                     name="hold", steps=16, own_live=True)
    for step in range(17, 41):
        _play(agent, step, health=20.0 if step < 24 else 14.0)
    assert "The plan was interrupted" in _notes(agent)


def test_the_first_call_of_an_entry_gets_the_cold_timeout(tmp_path: Path, monkeypatch):
    from mcu_worldmodel import own
    seen: list[float] = []
    real = own.run

    def spy(proc, root, state, args, timeout=own.TIMEOUT_S):
        seen.append(timeout)
        return real(proc, root, state, args, timeout=timeout)

    monkeypatch.setattr(own, "run", spy)
    _life(tmp_path, FOLLOW, {"procedure": "follow", "args": {"ticks": 40}}, own_live=True)
    assert own.LOOP_COLD_TIMEOUT_S > own.LOOP_TIMEOUT_S
    assert seen[0] == own.LOOP_COLD_TIMEOUT_S and seen[1:] == [own.LOOP_TIMEOUT_S] * 3


SIZE = '''"""size: one call; writes the frame size it was told and the size the PNG has."""
import json, sys
from PIL import Image
LOOP = True
s = json.load(sys.stdin)
with open("mine/size_calls.jsonl", "a") as f:
    f.write(json.dumps({"told": s.get("frame_size"), "png": list(Image.open(s["frame"]).size)}) + "\\n")
print(json.dumps({"actions": [{"action": {"sneak": 1}, "repeat": 2}], "again": False}))
'''


def test_the_live_frame_is_at_the_render_size_and_says_so(tmp_path: Path):
    agent, _ = _life(tmp_path, SIZE, {"procedure": "size", "args": {"ticks": 10}},
                     name="size", steps=20, own_live=True)
    rows = _calls(agent, "size")
    assert rows and rows[0]["told"] == rows[0]["png"] == [640, 360]
    # the episodes keep the run's smaller frame
    assert tuple(agent.frame_size) == (320, 180)
    from PIL import Image
    ep = next((agent.memory.root / "episodes").glob("ep_*/observation/image.png"))
    assert Image.open(ep).size == (320, 180)


def test_a_reflexs_previous_sample_does_not_cross_a_plan_boundary(tmp_path: Path):
    rec = ('"""rec: writes health and health_prev at every check; never fires."""\n'
           'import json, sys\ns = json.load(sys.stdin)\n'
           'open("mine/rec.jsonl", "a").write(json.dumps({"step": s["step"], '
           '"health": s["health"], "prev": s["health_prev"]}) + "\\n")\n')
    d = tmp_path / "ws" / "mine" / "reflexes"
    d.mkdir(parents=True)
    (d / "rec.py").write_text(rec)
    script = [{"actions": {"actions": [{"action": {"sneak": 1}, "repeat": 12}]},
               "message": "[PLAN]\nwait"}] * 6
    agent, _ = drive_chassis(tmp_path, "mfm", steps=12, script=script, **_arm("mfm"))
    # play on at health 20 until a plan ends; the next plan starts at health 18. The
    # plan is requested in next_action and the reflex check runs in observe, so at the
    # boundary step the stale sample is seeded first, the plan is enqueued, and any
    # check of that step comes after.
    boundary = None
    for step in range(13, 60):
        if boundary is None and step > 16 and not agent.queue:
            boundary = step
            agent._own_reflex_prev = {"health": 20.0, "food": 20.0, "pos": {"x": 0, "y": 64, "z": 0}}
        _play(agent, step, health=20.0 if boundary is None else 18.0)
        if boundary == step:
            assert (agent._own_reflex_prev or {"health": 18.0})["health"] == 18.0
        if boundary is not None and step >= boundary + 8:
            break
    assert boundary is not None
    rows = [json.loads(l) for l in (agent.memory.root / "mine" / "rec.jsonl").read_text().splitlines()]
    after = [r for r in rows if r["step"] >= boundary]
    assert after and all(r["health"] == 18.0 for r in after)
    # no check of the new plan sees the old plan's last sample as "4 ticks ago"
    assert all(r["prev"] == 18.0 for r in after), after
