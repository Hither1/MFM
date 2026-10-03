"""`--skills` (mcu_worldmodel/skills.py): the meta-level skill package (four
SKILL.md + example scripts) written into skills/, the starter reflexes installed under
mine/reflexes/, `--no-harness-reflexes` (the runner's guards off, the survival text says
so), the sweep keeping skills/."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = {"step": 40, "max_steps": 100,
        "pos": {"x": 1.0, "y": 60.0, "z": 1.0, "pitch": 8.0, "yaw": 0.0},
        "health": 16.0, "food": 18.0, "inventory": {},
        "hotbar": [{"slot": 0, "item": "diamond_pickaxe", "n": 1}, {"slot": 2, "item": "torch", "n": 8}],
        "gui_open": False, "dimension": "the Overworld", "lava_frac": 0.0,
        "health_prev": 16.0, "food_prev": 18.0,
        "pos_prev": {"x": 1.0, "y": 60.0, "z": 0.5, "pitch": 8.0, "yaw": 0.0},
        "entry": "go_to", "queue_len": 10, "runner_reflex": None}


def _run(path: Path, state: dict, args=None):
    cp = subprocess.run([sys.executable, str(path)] + (args or []), input=json.dumps(state),
                        capture_output=True, text=True, cwd=str(path.parents[2]))
    out = cp.stdout.strip()
    return cp.returncode, (json.loads(out) if out else None), cp.stderr.strip()


def test_write_skills_and_reflex_examples(tmp_path: Path):
    from mcu_worldmodel import skills

    written = skills.write_skills(tmp_path)
    assert {"skills/memory/SKILL.md", "skills/procedures/SKILL.md", "skills/reflexes/SKILL.md", "skills/reflexes/scripts/known_hazards.py", "skills/memory/scripts/death_sheet.py",
            "skills/harness/SKILL.md", "skills/procedures/scripts/stair_step.py",
            "skills/procedures/scripts/torch_wall.py", "skills/memory/scripts/where_was.py",
            "skills/reflexes/scripts/lava_ahead.py", "skills/reflexes/scripts/fell.py",
            "skills/reflexes/scripts/hit.py", "skills/reflexes/scripts/starving.py",
            "skills/procedures/scripts/shaft_down.py", "skills/procedures/scripts/strip_segment.py",
            "skills/procedures/scripts/aim_speckles.py"} == set(written)
    assert not (tmp_path / "mine").exists()                       # nothing installed: the model copies
    assert "Nothing is installed for you" in (tmp_path / "skills" / "reflexes" / "SKILL.md").read_text()
    for name in ("memory", "procedures", "reflexes", "harness"):
        text = (tmp_path / "skills" / name / "SKILL.md").read_text()
        assert text.startswith("---\nname: " + name)
        assert "-30" not in text and "5572" not in text          # no world facts
    assert "previous/life_<i>/" in (tmp_path / "skills" / "memory" / "SKILL.md").read_text()
    assert "workshop" in (tmp_path / "skills" / "memory" / "SKILL.md").read_text().lower()
    assert "One-block scripts" in (tmp_path / "skills" / "procedures" / "SKILL.md").read_text()
    assert "BEFORE the event" in (tmp_path / "skills" / "reflexes" / "SKILL.md").read_text()
    assert "Do not pour your only water bucket" in (tmp_path / "skills" / "harness" / "SKILL.md").read_text()
    # idempotent: the package is written once, like references/
    assert skills.write_skills(tmp_path) == []


def test_example_reflexes_fire_on_their_class_only(tmp_path: Path):
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path)
    rx = tmp_path / "skills" / "reflexes" / "scripts"
    # lava: moving toward it fires; standing at it on purpose does not
    rc, res, err = _run(rx / "lava_ahead.py", dict(BASE, lava_frac=0.2))
    assert rc == 0 and res["stop"] is True and "20%" in res["note"] and res["actions"][0]["action"] == {"back": 1}
    assert _run(rx / "lava_ahead.py", dict(BASE, lava_frac=0.2, entry="fill_bucket"))[1] is None
    still = dict(BASE, lava_frac=0.2, pos_prev=dict(BASE["pos"]))
    assert _run(rx / "lava_ahead.py", still)[1] is None
    assert _run(rx / "lava_ahead.py", dict(still, entry="mine_ahead"))[1] is not None
    assert _run(rx / "lava_ahead.py", dict(BASE, lava_frac=0.02))[1] is None          # 2% on the surface: a distant lake
    deep = dict(BASE, lava_frac=0.02, pos=dict(BASE["pos"], y=30.0), pos_prev=dict(BASE["pos_prev"], y=30.0))
    assert _run(rx / "lava_ahead.py", deep)[1] is not None                            # 2% at y 30: close
    assert _run(rx / "lava_ahead.py", dict(BASE, lava_frac=0.02, dimension="the Nether"))[1] is not None
    # fell: 3+ blocks down in four ticks
    rc, res, _ = _run(rx / "fell.py", dict(BASE, pos_prev=dict(BASE["pos"], y=64.0)))
    assert res["stop"] is True and res["note"].startswith("dropping 4.0 blocks in four ticks, a fall, now at (1, 60, 1)")
    assert _run(rx / "fell.py", dict(BASE, pos_prev=dict(BASE["pos"], y=61.5)))[1] is None
    # hit: a loss with no lava is a mob; with lava it is the lava's (another reflex's job)
    rc, res, _ = _run(rx / "hit.py", dict(BASE, health=11.0))
    assert res["stop"] is True and "took 5 damage (health 11/20)" in res["note"]
    assert _run(rx / "hit.py", dict(BASE, health=11.0, lava_frac=0.3))[1] is None
    assert _run(rx / "hit.py", dict(BASE, health=15.0))[1] is None
    # starving: the bar dropping below 18 -- eat what you carry (no stop),
    # else one note at the 18 crossing; a stop at health 10.5 with nothing to eat; nothing at
    # a steady bar, with a GUI open, or at the old <= 6 crossing
    rc, res, _ = _run(rx / "starving.py", dict(BASE, food=17.0))
    assert rc == 0 and res and "stop" not in res and "actions" not in res and "no natural healing" in res["note"]
    assert _run(rx / "starving.py", dict(BASE, food=15.0, food_prev=15.0))[1] is None
    assert _run(rx / "starving.py", dict(BASE, food=5.0, food_prev=7.0))[1] is None
    rc, res, _ = _run(rx / "starving.py", dict(BASE, food=17.0, inventory={"cobblestone": 30, "mutton": 2}))
    assert rc == 0 and res["actions"] == [{"procedure": "eat", "args": {"item": "mutton"}}] and "stop" not in res
    rc, res, _ = _run(rx / "starving.py", dict(BASE, food=13.0, food_prev=14.0, inventory={"cooked_beef": 1, "mutton": 2}))
    assert res["actions"][0]["args"]["item"] == "cooked_beef"                  # cooked first
    rc, res, _ = _run(rx / "starving.py", dict(BASE, food=17.0, inventory={"mutton": 2}, gui_open=True))
    assert "actions" not in res and "stop" not in res and "once the GUI is closed" in res["note"]   # no eat under a GUI
    assert _run(rx / "starving.py", dict(BASE, food=15.0, food_prev=15.0, inventory={"mutton": 2}))[1] is None
    assert _run(rx / "starving.py", dict(BASE, food=13.0, food_prev=14.0, inventory={"mutton": 2}, entry="eat"))[1] is None   # an eat in progress
    rc, res, _ = _run(rx / "starving.py", dict(BASE, health=10.2, health_prev=11.0, food=12.0, food_prev=12.0))
    assert res["stop"] is True and "cannot heal" in res["note"]
    assert _run(rx / "starving.py", dict(BASE, health=10.2, health_prev=10.2, food=12.0, food_prev=12.0))[1] is None
    assert _run(rx / "starving.py", dict(BASE, health=10.2, health_prev=11.0, food=12.0, food_prev=12.0, inventory={"mutton": 1}))[1] is None
    # the example procedures print valid plans; the guards refuse the wrong pose
    sp = tmp_path / "skills" / "procedures" / "scripts"
    rc, res, _ = _run(sp / "stair_step.py", BASE, ["--args", "{}"])
    assert rc == 0 and res["actions"][0] == {"procedure": "equip_hotbar", "args": {"slot": 1}}
    # raw attack holds, one per block: the holds the wall watcher samples under the atom set
    assert [a["repeat"] for a in res["actions"] if a.get("action") == {"attack": 1}] == [30, 30]
    rc, _, err = _run(sp / "stair_step.py", dict(BASE, pos=dict(BASE["pos"], y=60.4)), ["--args", "{}"])
    assert rc != 0 and "solid ground" in err
    rc, res, _ = _run(sp / "torch_wall.py", BASE, ["--args", "{}"])
    assert rc == 0 and res["actions"][1]["args"]["item"] == "torch" and res["actions"][1]["args"]["face"] == "west"


def test_sweep_keeps_skills(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory

    mem = MultimodalMemory(tmp_path / "a", episodes=True, own=True)
    (mem.root / "skills" / "memory").mkdir(parents=True)
    (mem.root / "skills" / "memory" / "SKILL.md").write_text("kept")
    (mem.root / "scratch.md").write_text("swept")
    removed = mem.sweep_foreign()
    assert "scratch.md" in removed and "skills" not in removed
    assert (mem.root / "skills" / "memory" / "SKILL.md").exists()


def test_survival_text_without_harness_reflexes():
    from mcu_worldmodel import prompts

    ref = prompts.action_reference(entry_cap=40, step_cap=400, memory_mode="mfm",
                                   task_family="from_scratch", atoms=True, harness_reflexes=False,
                                   own_reflexes=True)
    assert "does not act for you" in ref and "mine/reflexes/" in ref
    bare = prompts.action_reference(entry_cap=40, step_cap=400, memory_mode="logbook",
                                    task_family="from_scratch", atoms=True,
                                    harness_reflexes=False)
    assert "does not act for you" in bare and "mine/reflexes/" not in bare
    assert "BUNKERS you" not in ref and "The Nether lock" not in ref
    ref2 = prompts.action_reference(entry_cap=40, step_cap=400, memory_mode="mfm",
                                    task_family="from_scratch", atoms=True)
    assert "does not act for you" not in ref2


def test_chassis_skills_and_no_harness_reflexes(tmp_path: Path):
    from test_pins_chassis import drive_chassis

    ws = tmp_path / "ws"
    script = [{"actions": {"actions": [{"action": {"forward": 1}, "repeat": 20}]},
               "message": "[PLAN]\nwalk"}] + [
        {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
         "message": f"[PLAN]\nchop {i}"} for i in range(24)]
    agent, _ = drive_chassis(tmp_path, "mfm", thin=True, own=True, atoms=True, own_reflexes=True,
                             harness_reflexes=False, skills=True, script=script, steps=90)
    assert agent.reflexes is False and agent.skills is True and agent.own_reflexes is True
    contract = (ws / "AGENTS.md").read_text()
    assert "**Skills.**" in contract and "skills/reflexes" in contract
    assert "**Your own reflexes.**" in contract
    assert "does not act for you" in (ws / "references" / "survival.md").read_text()
    for name in ("memory", "procedures", "reflexes", "harness"):
        assert (ws / "skills" / name / "SKILL.md").exists()               # survived the sweeps
    # nothing installed under mine/reflexes/: the examples wait under skills/reflexes/scripts/
    assert not list((ws / "mine" / "reflexes").glob("*.py")) if (ws / "mine" / "reflexes").exists() else True
    assert {p.name for p in (ws / "skills" / "reflexes" / "scripts").glob("*.py")} >= {"lava_ahead.py", "fell.py", "hit.py", "starving.py", "known_hazards.py"}
    log = (ws / "logs.txt").read_text()
    assert "governor:" not in log and "NETHER LOCK" not in log
    assert "The runner is turning you" not in log and "BUNKERING" not in log
    assert agent.cursor_stats.get("own_reflex_runs", 0) == 0          # nothing installed, nothing ran (the loop: test_own_reflex.py)
    assert not agent.cursor_stats.get("own_reflex_failures")
    assert not any("`fell` -- fell:" in p for p in agent.codex.prompts)   # nothing installed: no reflex listed
    r = agent.report()
    assert r["skills"] is True and r["harness_reflexes"] is False and r["own"]["reflexes"] == 0   # nothing installed


def test_strip_segment_looks_at_the_next_floor_before_every_step(tmp_path: Path):
    """Two lives died in pools the camera had never looked at: the example strips look at the
    opened column's floor (pitch 65) and hold a watch there, so a reflex samples that view,
    before each forward step; shaft_down stops at y 13 by default."""
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path)
    sp = tmp_path / "skills" / "procedures" / "scripts"
    rc, res, err = _run(sp / "strip_segment.py", dict(BASE, pos=dict(BASE["pos"], x=1.5, z=1.5)), ["--args", "{}"])
    assert rc == 0, err
    acts = res["actions"]
    steps = [i for i, a in enumerate(acts) if a.get("action") == {"forward": 1}]
    assert len(steps) == 4
    for i in steps:
        assert acts[i - 1] == {"procedure": "watch", "args": {"n": 4}}
        assert acts[i - 2]["procedure"] == "look_abs" and acts[i - 2]["args"]["pitch"] == 65
    rc, res, err = _run(sp / "shaft_down.py", dict(BASE, pos=dict(BASE["pos"], x=1.5, z=1.5)), ["--args", "{}"])
    assert rc == 0, err
    mine = next(a for a in res["actions"] if a.get("procedure") == "mine_ahead")
    assert mine["args"]["n"] == min(370, (60 - 13) * 15, (60 - 12) * 12)          # diamond pickaxe: 15 planned, 12 soft
    rc, _, err = _run(sp / "shaft_down.py", dict(BASE, pos=dict(BASE["pos"], x=1.5, z=1.5, y=13.0)), ["--args", "{}"])
    assert rc != 0 and "at or below the target y 13" in err


def test_lava_reflex_stops_at_a_look_and_climbs_out_of_lava(tmp_path: Path):
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path)
    rx = tmp_path / "skills" / "reflexes" / "scripts"
    deep = dict(BASE, pos=dict(BASE["pos"], y=13.0), pos_prev=dict(BASE["pos_prev"], y=13.0))
    # a look or a watch that shows lava: stop, no step back (nothing moved)
    rc, res, _ = _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="watch", pos_prev=dict(deep["pos"])))
    assert res["stop"] is True and "actions" not in res and "at a watch" in res["note"]
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="look_abs", pos_prev=dict(deep["pos"])))[1] is not None
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.01, entry="watch", pos_prev=dict(deep["pos"])))[1] is None
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="place_at", pos_prev=dict(deep["pos"])))[1] is None
    # a watch with nothing queued after it (the model looking at the pool on purpose): quiet
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="watch", queue_len=1, pos_prev=dict(deep["pos"])))[1] is None
    # inside an own procedure the atom decides, not the script's name
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="strip_segment", atom="look_abs", pos_prev=dict(deep["pos"])))[1] is not None
    assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.05, entry="strip_segment", pos_prev=dict(deep["pos"])))[1] is None
    # in the lava (burning, between block levels): climb, placing the carried cobblestone
    inlava = dict(deep, lava_frac=0.4, health=12.0, health_prev=16.0, entry="raw",
                  pos=dict(deep["pos"], y=9.6), hotbar=BASE["hotbar"] + [{"slot": 4, "item": "cobblestone", "n": 20}])
    rc, res, _ = _run(rx / "lava_ahead.py", inlava)
    assert res["stop"] is True and res["note"].startswith("IN LAVA at (1, 9.6, 1)")
    # a flow at feet level over stone: y is integral and the climb is the same
    rc, res2, _ = _run(rx / "lava_ahead.py", dict(inlava, pos=dict(inlava["pos"], y=12.0)))
    assert res2["stop"] is True and res2["actions"] == res["actions"], res2
    assert res["actions"] == [{"procedure": "equip_hotbar", "args": {"slot": 5}},
                              {"action": {"back": 1, "jump": 1, "use": 1}, "repeat": 10}]
    rc, res, _ = _run(rx / "lava_ahead.py", dict(inlava, hotbar=BASE["hotbar"]))
    assert res["actions"] == [{"action": {"back": 1, "jump": 1}, "repeat": 10}]
    # hit with a block carried: pillar up; without one, the note alone
    rc, res, _ = _run(rx / "hit.py", dict(BASE, health=11.0, hotbar=BASE["hotbar"] + [{"slot": 4, "item": "dirt", "n": 3}]))
    assert res["stop"] is True and res["actions"] == [{"procedure": "pillar_up", "args": {"n": 2}}] and "pillared up" in res["note"]
    rc, res, _ = _run(rx / "hit.py", dict(BASE, health=11.0))
    assert res["stop"] is True and "actions" not in res


def test_lava_reflex_leaves_flames_to_the_plan_and_escapes_on_lava_damage(tmp_path: Path):
    """The recorded case: a life lit its portal from inside -- on those frames fire_frac
    read 0.45-0.56 against lava_frac 0.03-0.24 and one health point went per fire tick --
    and the old in-lava escape (any health drop with orange >= 20%) pulled it back into
    the fire. Lava takes 4 health every 10 ticks, fire 1 every 20, so the escape keys on
    a loss of 3+ between samples; flames (fire_frac >= 0.2 and > 2x lava_frac) are left
    to the plan; a lake ahead reads fire_frac BELOW lava_frac and still stops a walk."""
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path)
    rx = tmp_path / "skills" / "reflexes" / "scripts"
    deep = dict(BASE, pos=dict(BASE["pos"], y=10.0), pos_prev=dict(BASE["pos_prev"], y=10.0))
    fire = dict(deep, lava_frac=0.055, fire_frac=0.524, entry="raw")              # the portal just lit
    assert _run(rx / "lava_ahead.py", fire)[1] is None
    burning = dict(deep, lava_frac=0.205, fire_frac=0.561, health=13.0, health_prev=14.0, entry="raw")
    assert _run(rx / "lava_ahead.py", burning)[1] is None                        # the old "IN LAVA at health 13"
    rc, res, _ = _run(rx / "lava_ahead.py", dict(burning, health=10.0, health_prev=14.0, lava_frac=0.3))
    assert res["stop"] is True and res["note"].startswith("IN LAVA")             # lava's 4-point bite: the escape
    rc, res, _ = _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.086, fire_frac=0.036, entry="go_to"))
    assert res["stop"] is True and "stepped back" in res["note"]                 # a lake ahead (life 3's frames)
    for e in ("use_at", "place_at", "fill_bucket", "use_held"):                  # at the pool or the fire by design
        assert _run(rx / "lava_ahead.py", dict(deep, lava_frac=0.3, fire_frac=0.5, health=10.0, health_prev=14.0, entry=e))[1] is None
    # hit: flames are not a mob, and no pillar in the middle of a placement
    assert _run(rx / "hit.py", dict(BASE, health=11.0, fire_frac=0.4))[1] is None
    rc, res, _ = _run(rx / "hit.py", dict(BASE, health=11.0, entry="place_at",
                                          hotbar=BASE["hotbar"] + [{"slot": 4, "item": "dirt", "n": 3}]))
    assert res["stop"] is True and "actions" not in res
    rc, res, _ = _run(rx / "hit.py", dict(BASE, health=11.0, entry="go_to",
                                          hotbar=BASE["hotbar"] + [{"slot": 4, "item": "dirt", "n": 3}]))
    assert res["actions"] == [{"procedure": "pillar_up", "args": {"n": 2}}]
