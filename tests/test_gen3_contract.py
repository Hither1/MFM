"""Generation-3 contract and skill package (2026-09-09): Routines / Rules of play / Improve
yourself in the minimal contract, the digest block beside [WORKING], the compact procedure
index, the codex-native skill catalog (`.agents/skills` mirroring skills/ and mine/skills/),
the six skills' trigger descriptions, the hit/burning/drowning reflex examples and the
atoms-aware cut-short hint. Run with MFM_MCU_ROOT pointing at the MCU checkout under test."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

MCU = Path(os.environ.get("MFM_MCU_ROOT", Path(__file__).resolve().parents[1] / "MCU"))
if str(MCU) not in sys.path:
    sys.path.insert(0, str(MCU))


def _contracts():
    from mcu_worldmodel import prompts
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    kw = dict(task_text="Kill the dragon", progress_block="0/24", entry_cap=40, step_cap=400,
              atoms=True, frames=True, harness_reflexes=False)
    carried = prompts.minimal_contract(previous=True, **kw)
    scratch = prompts.minimal_contract(previous=False, **kw)
    P.set_visible(None)
    return carried, scratch


def test_minimal_contract_carries_routines_rules_and_self_improvement():
    carried, scratch = _contracts()
    for must in ("**Routines**", "workshop turn (`skills/memory/SKILL.md`)", "death_sheet.py",
                 "three plans in a row that moved", "`[RECALL]` block",
                 "**Rules of play**", "never replay a resource-consuming sequence",
                 "obsidian: the diamond pickaxe only", "No natural healing below 18 food",
                 "`skills/minecraft`", "`skills/mining`",
                 "**Improve yourself.**", "mine/skills/<name>/SKILL.md", "write the reflex now",
                 "`mine/digest.md` (what is true of this world across lives)",
                 "Your context does not persist between turns", "--ores", "--y-profile"):
        assert must in carried, must
    # the workshop routine belongs to lives with previous/ only; the rest is shared
    assert "workshop turn" not in scratch and "**Previous lives.**" not in scratch
    assert "**Routines**" in scratch and "**Rules of play**" in scratch
    # the contract is read at the start of every session: keep it priced
    assert len(carried.encode()) < 14000, len(carried.encode())
    # rules, not places: no world coordinate anywhere in the contract
    assert not re.search(r"\(-?\d{3,}\.?\d*,\s*-?\d", carried)


def test_compact_procedure_index_keeps_names_and_defaults_only():
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    compact, full = P.index(compact=True), P.index()
    P.set_visible(None)
    assert "`go_to(x, z, within=1.5, n)`" in compact
    assert "=<" not in compact and "=<" in full
    assert len(compact) < 0.8 * len(full)
    assert compact.count("\n") == full.count("\n")           # every atom is still listed


def test_skill_package_has_six_trigger_skills_and_a_native_catalog(tmp_path: Path):
    from mcu_worldmodel import skills as K
    written = K.write_skills(tmp_path)
    names = sorted(p.name for p in (tmp_path / "skills").iterdir())
    assert names == ["harness", "memory", "minecraft", "mining", "procedures", "reflexes"]
    for n in names:
        text = (tmp_path / "skills" / n / "SKILL.md").read_text()
        desc = re.search(r"^description: (.*)$", text, re.M).group(1)
        assert desc.startswith("Use "), (n, desc[:60])         # a trigger, not a summary
        assert not re.search(r"\(-?\d{3,}\.?\d*,\s*-?\d", text), n  # rules, not places
    mc = (tmp_path / "skills" / "minecraft" / "SKILL.md").read_text()
    assert "4 wide x 5 tall" in mc and "18 or more" in mc and "DIAMOND pickaxe" in mc
    mn = (tmp_path / "skills" / "mining" / "SKILL.md").read_text()
    assert "--y-profile" in mn and "Principles" in mn and "Expose, then look, then break" in mn
    assert "every 3rd block" not in mn and "every 8-10 blocks" not in mn      # principles, not a recipe (user, 2026-09-09)
    # the codex-native catalog: .agents/skills/<name> -> ../../skills/<name>, resolving to SKILL.md
    cat = tmp_path / ".agents" / "skills"
    assert sorted(p.name for p in cat.iterdir()) == names
    for n in names:
        assert (cat / n).is_symlink() and (cat / n / "SKILL.md").is_file()
        assert os.readlink(cat / n) == f"../../skills/{n}"
    # the model's own skills join the catalog on sync, and leave it when deleted
    own = tmp_path / "mine" / "skills" / "portal_check"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("---\nname: portal_check\ndescription: Use before igniting.\n---\n")
    (tmp_path / "mine" / "skills" / "half").mkdir()             # no SKILL.md: not a skill
    linked = K.sync_skill_catalog(tmp_path)
    assert "portal_check" in linked and "half" not in linked
    assert os.readlink(cat / "portal_check") == "../../mine/skills/portal_check"
    assert (cat / "portal_check" / "SKILL.md").is_file()
    (own / "SKILL.md").unlink()
    K.sync_skill_catalog(tmp_path)
    assert not (cat / "portal_check").exists() and not (cat / "portal_check").is_symlink()
    assert "skills/reflexes/scripts/burning.py" in written and "skills/reflexes/scripts/drowning.py" in written
    assert "mine/skills/<name>" in K.SKILLS_NOTE and "`minecraft`, `mining`" in K.SKILLS_NOTE


def _run_reflex(tmp_path: Path, name: str, state: dict) -> dict | None:
    from mcu_worldmodel import skills as K
    script = tmp_path / "skills" / "reflexes" / "scripts" / name
    if not script.exists():
        K.write_skills(tmp_path)
    out = subprocess.run([sys.executable, str(script)], input=json.dumps(state), text=True,
                         capture_output=True, timeout=30, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def test_reflex_examples_name_the_unknown_source_fire_and_water(tmp_path: Path):
    pos = {"x": 1.0, "y": 11.0, "z": 2.0, "pitch": 0.0, "yaw": 0.0}
    base = {"pos": pos, "pos_prev": pos, "health": 9.0, "health_prev": 10.0, "food": 15, "food_prev": 15,
            "lava_frac": 0.0, "fire_frac": 0.0, "water_frac": 0.0, "hotbar": [], "entry": "mine_ahead",
            "gui_open": False, "dimension": "overworld"}
    hit = _run_reflex(tmp_path, "hit.py", {**base, "health": 6.0})
    assert hit and hit["stop"] and "source unknown" in hit["note"] and "mob is at you" not in hit["note"]
    burn = _run_reflex(tmp_path, "burning.py", {**base, "lava_frac": 0.05,
                                                  "hotbar": [{"slot": 8, "item": "water_bucket"}]})
    assert burn and burn["stop"] and "BURNING" in burn["note"] and "water bucket" in burn["note"]
    assert "actions" not in burn                                  # no automatic step back
    walking = {**base, "lava_frac": 0.05, "pos_prev": {**pos, "x": 3.5}}
    assert _run_reflex(tmp_path, "burning.py", walking) is None   # a walk: lava_ahead's job
    # starving: a note at the 18 crossing, a STOP when health is low with no healing or food is nearly out
    st = _run_reflex(tmp_path, "starving.py", {**base, "health": 12.0, "health_prev": 12.0, "food": 17, "food_prev": 18})
    assert st and "stop" not in st and "no natural healing below 18" in st["note"]
    st2 = _run_reflex(tmp_path, "starving.py", {**base, "health": 9.0, "health_prev": 12.0, "food": 15, "food_prev": 15})
    assert st2 and st2["stop"] and "cannot heal" in st2["note"]
    st3 = _run_reflex(tmp_path, "starving.py", {**base, "health": 18.0, "health_prev": 18.0, "food": 5, "food_prev": 7})
    assert st3 and st3["stop"]
    assert _run_reflex(tmp_path, "starving.py", {**base, "health": 18.0, "health_prev": 18.0, "food": 15, "food_prev": 15}) is None
    drown = _run_reflex(tmp_path, "drowning.py", {**base, "water_frac": 0.6})
    assert drown and drown["stop"] and "DROWNING" in drown["note"]
    assert drown["actions"][0]["action"] == {"jump": 1}
    assert _run_reflex(tmp_path, "drowning.py", base) is None


def test_digest_block_beside_working_and_the_forty_line_rule(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent

    class Mem:
        root = tmp_path

    class Fake:
        own = True
        memory = Mem()
        WORKING_CAP = WorldModelAgent.WORKING_CAP
    fake = Fake()
    assert WorldModelAgent._digest_block(fake) == ""
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "digest.md").write_text("# life_1\n- iron at the shallow face, step 5300\n")
    block = WorldModelAgent._digest_block(fake)
    assert block.startswith("[DIGEST] mine/digest.md") and "shallow face" in block
    (tmp_path / "mine" / "digest.md").write_text("y" * 5000)
    assert "3000 more chars: Read mine/digest.md" in WorldModelAgent._digest_block(fake)
    (tmp_path / "mine" / "working.md").write_text("\n".join(f"line {i}" for i in range(50)))
    w = WorldModelAgent._working_block(fake)
    assert "[working.md is 50 lines; the contract asks for 40" in w
    (tmp_path / "mine" / "working.md").write_text("\n".join(f"line {i}" for i in range(20)))
    assert "the contract asks for" not in WorldModelAgent._working_block(fake)
    fake.own = False
    assert WorldModelAgent._digest_block(fake) == ""


def test_cut_short_hint_names_tools_that_exist_in_this_run():
    from mcu_worldmodel.agent import _cut_short_hint
    assert "mine_ahead" in _cut_short_hint(True) and "mine_forward" not in _cut_short_hint(True)
    assert "mine_forward/strip_mine/stair_down" in _cut_short_hint(False)


def test_compactions_are_counted_from_the_rollout(tmp_path: Path):
    """codex 0.147 writes `{"type":"compacted"}` records into the session rollout and nothing
    into the `exec --json` stream; the stream counter read 0 against rollouts holding 28-96."""
    from mcu_worldmodel import codex_backend as cb
    roll = tmp_path / "rollout-2026-09-09T00-00-00-abc.jsonl"
    lines = ['{"timestamp":"t","type":"session_meta","payload":{}}',
             '{"timestamp":"t","type":"compacted","payload":{"message":"summary"}}',
             '{"timestamp":"t","type":"response_item","payload":{"type":"message"}}',
             '{"timestamp":"t","type":"compacted","payload":{"message":"summary 2"}}',
             '{"timestamp":"t","type":"compacted","payload":{}}']
    roll.write_text("\n".join(lines) + "\n")
    counts = cb.scan_rollout(roll)
    assert counts["compactions"] == 3 and counts["view_image_calls"] == 0
    assert cb.scan_rollout(tmp_path / "missing.jsonl")["compactions"] == 0


def test_gui_open_settles_and_a_mined_station_leaves_the_map():
    """The frame trails isGuiOpen: the open loop idles GUI_OPEN_SETTLE ticks after the flag
    flips; a crafting_table or furnace mined back up is dropped from the placed records."""
    from types import SimpleNamespace
    from mcu_worldmodel.agent import WorldModelAgent, GUI_OPEN_SETTLE
    from mcu_worldmodel import gui

    def mk_act(**kw):
        return {"action": kw or {"noop": 1}}
    fake = SimpleNamespace(_gui_open=True)
    og = {"attempts": 3, "t": 0}
    idle = [WorldModelAgent._opengui_tick(fake, og, mk_act) for _ in range(GUI_OPEN_SETTLE)]
    assert all(a == {"action": {"noop": 1}} for a in idle) and GUI_OPEN_SETTLE >= 2
    assert WorldModelAgent._opengui_tick(fake, og, mk_act) is None       # then the entry ends
    fake._gui_open = False
    assert WorldModelAgent._opengui_tick(fake, {"attempts": 3, "t": 0}, mk_act) == {"action": {"inventory": 1}}
    assert gui.CRAFT_SETTLE >= 6
    notes = []
    ag = SimpleNamespace(_placed={"furnace": (1, 64, 2)}, grid=SimpleNamespace(placed={"furnace": {"cell": (1, 64, 2)}}),
                         memory=SimpleNamespace(add_note=notes.append))
    WorldModelAgent._station_picked_up(ag, "furnace", 28914)
    assert ag._placed == {} and ag.grid.placed == {} and "mined your furnace back up at step 28914" in notes[0]
    WorldModelAgent._station_picked_up(ag, "crafting_table", 1)         # nothing placed: silent
    assert len(notes) == 1
