"""Generation-4 contract and skill package (2026-09-10, the FULL arm of the gen-4 head-to-head):
gen 2's minimal contract with the gen-3 neutral fixes and without its doctrine -- no Routines,
Rules of play, Improve yourself or persistence sentence; the workshop sentence is gen 2's; the
three gen-4 edits (the starving example eats, the hunger line in Safety, then-now on arrival
and the episode id beside every digest place); four skills and no codex-native catalog; the
game rules as references/minecraft.md; slow_loss.py in place of drowning.py; the digest block
beside [WORKING], the compact procedure index, the atoms-aware cut-short hint. Run with
MFM_MCU_ROOT pointing at the MCU checkout under test."""
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


def test_minimal_contract_is_gen_2_plus_the_three_edits():
    carried, scratch = _contracts()
    for must in ("workshop turn (`skills/memory/SKILL.md`): read them before you play",
                 "./tools/episodes.py --then-now <that episode> --q \"...\"`\nonce (this life's, or an earlier life's under `previous/`)",
                 "Natural healing needs the food bar at 18+", "eat when the bar is below 18",
                 "every place with the episode whose frame shows it",
                 "shown\nunasked only at the start of a life", "one look per plan is the budget",
                 "do not spend a cell\nvalidating it yourself", "--ores", "--y-profile"):
        assert must in carried, must
    # gen 3's doctrine is gone: the 16/24 life never had it (analysis/gen4_plan_2026-09-10.md)
    for gone in ("**Routines**", "**Rules of play**", "**Improve yourself", "death_sheet.py",
                 "three plans in a row", "A plan runs open-loop", "never replay a resource-consuming",
                 "mine/skills/<name>/SKILL.md", "Your context does not persist", "Your thread persists",
                 "`skills/minecraft`", "`skills/mining`", "[RECALL]"):
        assert gone not in carried, gone
    assert "workshop turn" not in scratch and "**Previous lives.**" not in scratch
    assert "Natural healing needs the food bar at 18+" in scratch
    assert len(carried.encode()) < 12000, len(carried.encode())
    assert not re.search(r"\(-?\d{3,}\.?\d*,\s*-?\d", carried)        # rules, not places


def test_one_thread_flag_changes_nothing_in_the_contract():
    from mcu_worldmodel import prompts
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    kw = dict(task_text="t", progress_block="p", entry_cap=8, step_cap=400,
              atoms=True, frames=True, harness_reflexes=False, previous=True)
    one = prompts.minimal_contract(one_thread=True, **kw)
    fresh = prompts.minimal_contract(one_thread=False, **kw)
    P.set_visible(None)
    assert one == fresh and "persist" not in one


def test_compact_procedure_index_keeps_names_and_defaults_only():
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    compact, full = P.index(compact=True), P.index()
    P.set_visible(None)
    assert "`go_to(x, z, within=1.5, n)`" in compact
    assert "=<" not in compact and "=<" in full
    assert len(compact) < 0.8 * len(full)
    assert compact.count("\n") == full.count("\n")           # every atom is still listed


def test_skill_package_is_gen_2s_four_skills_and_the_minecraft_reference(tmp_path: Path):
    from mcu_worldmodel import skills as K
    written = K.write_skills(tmp_path)
    names = sorted(p.name for p in (tmp_path / "skills").iterdir())
    assert names == ["harness", "memory", "procedures", "reflexes"]
    for n in names:
        text = (tmp_path / "skills" / n / "SKILL.md").read_text()
        desc = re.search(r"^description: (.*)$", text, re.M).group(1)
        assert not desc.startswith("Use "), (n, desc[:60])     # gen 2's summaries, not gen 3's triggers
        assert not re.search(r"\(-?\d{3,}\.?\d*,\s*-?\d", text), n
    assert not (tmp_path / ".agents").exists()                   # no codex-native catalog
    assert "Read all\nfour in your first turn" in K.SKILLS_NOTE and "mine/skills" not in K.SKILLS_NOTE
    assert "the episode id whose frame shows the place" in (tmp_path / "skills" / "memory" / "SKILL.md").read_text()
    rx = (tmp_path / "skills" / "reflexes" / "SKILL.md").read_text()
    assert "`slow_loss.py`" in rx and "drowning.py" not in rx and "`health_100` (100 ticks ago)" in rx
    assert "skills/reflexes/scripts/slow_loss.py" in written and "skills/reflexes/scripts/drowning.py" not in written
    mc = K.MINECRAFT_REFERENCE
    for must in ("# Minecraft: the rules this world follows", "4 wide x 5 tall", "18 or more", "DIAMOND pickaxe",
                 "respawn", "BED", "GOLD armour", "eight in the Overworld", "The void",
                 "Bow = 3 sticks + 3 string", "silverfish", "iron cages", "Piglins",
                 "## Finding ore you have never seen", "--y-profile"):
        assert must in mc, must
    assert not mc.startswith("---") and not re.search(r"\(-?\d{3,}\.?\d*,\s*-?\d", mc)
    assert "every 3rd block" not in mc and "every 8-10 blocks" not in mc  # principles, not a recipe


def _run_reflex(tmp_path: Path, name: str, state: dict) -> dict | None:
    from mcu_worldmodel import skills as K
    script = tmp_path / "skills" / "reflexes" / "scripts" / name
    if not script.exists():
        K.write_skills(tmp_path)
    out = subprocess.run([sys.executable, str(script)], input=json.dumps(state), text=True,
                         capture_output=True, timeout=30, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout) if out.stdout.strip() else None


def test_reflex_examples_name_the_unknown_source_fire_and_the_slow_loss(tmp_path: Path):
    pos = {"x": 1.0, "y": 11.0, "z": 2.0, "pitch": 0.0, "yaw": 0.0}
    base = {"pos": pos, "pos_prev": pos, "health": 9.0, "health_prev": 10.0, "food": 15, "food_prev": 15,
            "lava_frac": 0.0, "fire_frac": 0.0, "water_frac": 0.0, "hotbar": [], "entry": "mine_ahead",
            "gui_open": False, "dimension": "overworld", "inventory": {}}
    hit = _run_reflex(tmp_path, "hit.py", {**base, "health": 6.0})
    assert hit and hit["stop"] and "source unknown" in hit["note"] and "mob is at you" not in hit["note"]
    burn = _run_reflex(tmp_path, "burning.py", {**base, "lava_frac": 0.05,
                                                  "hotbar": [{"slot": 8, "item": "water_bucket"}]})
    assert burn and burn["stop"] and "BURNING" in burn["note"] and "water bucket" in burn["note"]
    assert "actions" not in burn                                  # no automatic step back
    walking = {**base, "lava_frac": 0.05, "pos_prev": {**pos, "x": 3.5}}
    assert _run_reflex(tmp_path, "burning.py", walking) is None   # a walk: lava_ahead's job
    # starving: eat what you carry when the bar drops below 18; a note with nothing to eat;
    # a stop at health 10.5 with nothing to eat
    st = _run_reflex(tmp_path, "starving.py", {**base, "health": 12.0, "health_prev": 12.0, "food": 17, "food_prev": 18})
    assert st and "stop" not in st and "actions" not in st and "nothing to eat" in st["note"]
    eat = _run_reflex(tmp_path, "starving.py", {**base, "health": 12.0, "health_prev": 12.0, "food": 17, "food_prev": 18,
                                                 "inventory": {"porkchop": 3}})
    assert eat and eat["actions"] == [{"procedure": "eat", "args": {"item": "porkchop"}}] and "stop" not in eat
    st2 = _run_reflex(tmp_path, "starving.py", {**base, "health": 10.0, "health_prev": 12.0, "food": 15, "food_prev": 15})
    assert st2 and st2["stop"] and "cannot heal" in st2["note"]
    assert _run_reflex(tmp_path, "starving.py", {**base, "health": 18.0, "health_prev": 18.0, "food": 5, "food_prev": 7}) is None
    assert _run_reflex(tmp_path, "starving.py", {**base, "health": 18.0, "health_prev": 18.0, "food": 15, "food_prev": 15}) is None
    # slow_loss: the drowning class without a water detector (dark water reads 0)
    slow = _run_reflex(tmp_path, "slow_loss.py", {**base, "health": 9.0, "health_prev": 9.5, "health_100": 12.5})
    assert slow and slow["stop"] and "100 ticks" in slow["note"] and "swim up" in slow["note"]
    assert _run_reflex(tmp_path, "slow_loss.py", {**base, "health": 9.0, "health_prev": 12.5, "health_100": 12.5}) is None
    assert _run_reflex(tmp_path, "slow_loss.py", {**base, "health": 9.0, "health_prev": 9.5, "health_100": 12.5, "fire_frac": 0.1}) is None
    assert _run_reflex(tmp_path, "slow_loss.py", base) is None


def test_digest_block_beside_working_and_the_forty_line_rule(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent

    class Mem:
        root = tmp_path

    class Fake:
        own = True
        memory = Mem()
        WORKING_CAP = WorldModelAgent.WORKING_CAP
        turns = {"act": 1}
    fake = Fake()
    assert WorldModelAgent._digest_block(fake) == ""
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "digest.md").write_text("# life_1\n- iron at the shallow face, step 5300\n")
    block = WorldModelAgent._digest_block(fake)
    assert block.startswith("[DIGEST] mine/digest.md") and "shallow face" in block
    (tmp_path / "mine" / "digest.md").write_text("y" * 5000)
    block = WorldModelAgent._digest_block(fake)
    assert "3000 more chars: Read mine/digest.md" in block and "5000 chars; the contract asks for 20" in block
    # from the third act turn on, a pointer, not the text (the model reads the file itself)
    fake.turns = {"act": 3}
    (tmp_path / "mine" / "digest.md").write_text("# life_1\n- iron at the shallow face, step 5300\n")
    block = WorldModelAgent._digest_block(fake)
    assert block.startswith("[DIGEST] mine/digest.md -- your across-lives facts, not shown") and "shallow face" not in block
    assert "rewrite it" not in block
    (tmp_path / "mine" / "digest.md").write_text("\n".join(f"Step{i} note" for i in range(207)))
    block = WorldModelAgent._digest_block(fake)
    assert "207 lines" in block and "rewrite it -- step notes belong in mine/notes.md" in block and "Step5" not in block
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


def test_atoms_references_are_macro_free_and_keep_recipes_and_write_down():
    """`--atoms`: references/skills.md is the engine's situations without the macro library
    (user, 2026-09-09: general knowledge, nothing task-shaped prescribed); survival.md's
    Movement bullets stop naming mine_forward/strip_mine/stair_down."""
    from mcu_worldmodel import prompts
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    full = prompts.act_prompt(task_text="Kill the dragon", progress_block="0/24", graph_summary="",
                              plan_summary="", discipline_summary="", entry_cap=40, step_cap=400,
                              memory_mode="mfm", retrieval=True, previous=True, expect=True,
                              frames=True, own=True, atoms=True, own_reflexes=True, harness_reflexes=False)
    P.set_visible(None)
    thin, refs = prompts.thin_split(full)
    orig = refs["skills.md"]
    assert "harvest_tree(" in orig and "fight_blaze()" in orig            # the macro-shaped original
    sk = prompts.situations_atoms(orig)
    for macro in ("harvest_tree(", "strip_mine(", "dig_down(", "make_obsidian(", "build_portal_frame(",
                  "light_portal(", "fight_blaze(", "enderman_pit(", "throw_eye(", "fill_end_portal(",
                  "enter_end(", "break_crystal(", "attack_dragon(", "sleep_in_bed(", "explore_nether(",
                  "fetch_water(", "scan_around(", "travel_bearing("):
        assert macro not in sk, macro
    for must in ("**Skills by situation**", "references/minecraft.md",
                 "COBBLESTONE block", "drop_and_pickup(slot)", "Entities are reported on no channel",
                 "divided by 8", "end_stone", "Recipes available:", "**Write down what worked"):
        assert must in sk, must
    assert len(sk) < 0.6 * len(orig), (len(sk), len(orig))
    sv = prompts.survival_atoms(refs["survival.md"])
    assert "mine_forward" in refs["survival.md"] and "mine_forward" not in sv
    assert "queue one `mine_ahead` per block" in sv and "**Turn, then move.**" in sv
    assert prompts.survival_atoms("unrelated text") == "unrelated text"
