"""The skill-reuse experiment's parts: the memory of a life as it stood at step T, and a
life that carries it into another world on another task.

    scripts/mine_history.py   what `mine/` held at each step, recorded beside the life
    scripts/memory_at.py      the life's record cut at T, with `mine/` from that history
    --carried-world other     the contract and the memory skill say the carried lives were
                              played elsewhere; "same" is the shipped text, byte for byte
                              (pinned in test_release_pins.py)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from conftest import MCU
from test_pins_chassis import drive_chassis
from test_release_pins import _arm

sys.path.insert(0, str(MCU / "scripts"))
import memory_at  # noqa: E402
import mine_history  # noqa: E402

HEADER = re.compile(r"^Action \d+ \| Step (\d+)", re.M)


def _life_with_history(tmp_path: Path):
    """One scripted life; `mine/` is rewritten twice and its history recorded as the
    poller would have, once per state."""
    agent, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    ws = agent.memory.root
    history = tmp_path / "history"
    steps = sorted({int(s) for s in HEADER.findall((ws / "logs.txt").read_text())})
    mid = steps[len(steps) // 2]
    # the state at `mid`: the log is cut there for the poller to read its step from
    full = (ws / "logs.txt").read_text()
    (ws / "logs.txt").write_text(memory_at.cut_log(full, mid)[0])
    (ws / "mine").mkdir(exist_ok=True)
    (ws / "mine" / "notes.md").write_text("early\n")
    last = mine_history.snapshot(ws, history, None)
    assert mine_history.snapshot(ws, history, last) == last        # no change, no row
    (ws / "logs.txt").write_text(full)
    (ws / "mine" / "notes.md").write_text("late\n")
    (ws / "mine" / "procedures").mkdir(exist_ok=True)
    (ws / "mine" / "procedures" / "dig.py").write_text("# written late\n")
    mine_history.snapshot(ws, history, last)
    return ws, history, mid, steps


def test_the_history_keeps_one_row_per_state_of_mine(tmp_path: Path):
    ws, history, mid, steps = _life_with_history(tmp_path)
    rows = mine_history.rows(history)
    assert [r["step"] for r in rows] == [mid, steps[-1]]
    assert mine_history.at(history, mid - 1) is None
    assert set(mine_history.at(history, mid)["files"]) == {"notes.md"}
    assert set(mine_history.at(history, steps[-1])["files"]) == {"notes.md", "procedures/dig.py"}


def test_the_cut_holds_what_had_ended_by_the_step(tmp_path: Path):
    ws, history, mid, steps = _life_with_history(tmp_path)
    out = tmp_path / "cut"
    info = memory_at.cut(ws, mid, out, history)

    kept = [int(s) for s in HEADER.findall((out / "logs.txt").read_text())]
    assert kept and max(kept) == mid and kept == [s for s in
        (int(x) for x in HEADER.findall((ws / "logs.txt").read_text())) if s <= mid]
    rows = [json.loads(l) for l in (out / "index.jsonl").read_text().splitlines()]
    whole = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines()]
    assert rows == [r for r in whole if int(r.get("last_step") or 0) <= mid]
    assert 0 < len(rows) < len(whole)
    assert sorted(p.name for p in (out / "episodes").iterdir()) == sorted(r["id"] for r in rows)
    assert all(json.loads(l)["step"] <= mid for l in (out / "grid.jsonl").read_text().splitlines())
    # mine/ is the early state, not the final one
    assert (out / "mine" / "notes.md").read_text() == "early\n"
    assert not (out / "mine" / "procedures" / "dig.py").exists()
    # machinery stays behind; the provenance is a dotfile the carry skips
    for name in ("AGENTS.md", "tools", "references", "actions.json"):
        assert not (out / name).exists()
    assert info["mine"]["row_step"] == mid and (out / ".cut.json").exists()


def test_a_step_inside_the_life_needs_the_history(tmp_path: Path):
    ws, history, mid, steps = _life_with_history(tmp_path)
    with pytest.raises(SystemExit, match="not recoverable"):
        memory_at.cut(ws, mid, tmp_path / "cut", None)
    whole = memory_at.cut(ws, steps[-1], tmp_path / "whole", None)
    assert whole["mine"]["from"] == "final"
    assert (tmp_path / "whole" / "mine" / "notes.md").read_text() == "late\n"


def test_a_cut_life_is_carried_and_said_to_be_another_world(tmp_path: Path):
    ws, history, mid, _ = _life_with_history(tmp_path)
    cut = tmp_path / "cut"
    memory_at.cut(ws, mid, cut, history)

    agent, _ = drive_chassis(tmp_path / "life_2", "mfm", previous_lives=[str(cut)],
                             carried_world="other", **_arm("mfm"))
    root = agent.memory.root
    life = root / "previous" / "life_1"
    assert (life / "mine" / "notes.md").read_text() == "early\n"
    assert not (life / ".cut.json").exists()
    carried = [json.loads(l) for l in (root / "previous" / "index.jsonl").read_text().splitlines()]
    assert carried and all(r["life"] == 1 and r["path"].startswith("previous/life_1/")
                           for r in carried)

    contract = (root / "AGENTS.md").read_text()
    assert "ANOTHER\nWORLD" in contract and "in another world and on another task" in contract
    assert "SAME WORLD" not in contract and "in this same world" not in contract
    skill = (root / "skills" / "memory" / "SKILL.md").read_text()
    assert "in ANOTHER world" in skill and "same seed, same spawn" not in skill
    assert "none of their coordinates" in skill


def test_other_world_needs_carried_lives_on_the_mfm_arm(tmp_path: Path):
    with pytest.raises(ValueError, match="carried_world"):
        drive_chassis(tmp_path, "mfm", carried_world="other", **_arm("mfm"))
    with pytest.raises(ValueError, match="carried_world"):
        drive_chassis(tmp_path, "mfm", carried_world="elsewhere", **_arm("mfm"))


def test_the_probe_tasks_share_an_opening_and_end_apart():
    from task_milestones import load_milestone_cfg
    chains = {t: [c["identity"] for c in load_milestone_cfg(t)]
              for t in ("cook_meat", "coal_torches", "iron_shield")}
    opening = ["mine_log", "crafting_table", "wooden_pickaxe", "cobblestone"]
    assert all(chain[:4] == opening for chain in chains.values())
    assert len({chain[-1] for chain in chains.values()}) == 3
    diamond = {c["identity"] for c in load_milestone_cfg("mine_diamond_from_scratch")}
    assert all(chain[-1] not in diamond for chain in chains.values())
    # every rule shows the model all of its objects: the checklist prints four
    assert all(len(c["objects"]) <= 4 for t in chains for c in load_milestone_cfg(t))


# ---- the second design: checkpoints are lives, probes run the iron tail --------------

TAIL_TASKS = ("iron_shield_tail", "shears_tail", "bucket_tail")


def _fake_life(root: Path, own: dict[str, str], shipped: dict[str, str]) -> Path:
    """A memory dir with shipped examples under skills/, and mine/ holding copies of them
    plus the files in `own` ("mine/<dir>/<name>": text)."""
    for name, text in shipped.items():
        d = "reflexes" if name in ("fell.py", "hit.py") else "procedures"
        (root / "skills" / d / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "skills" / d / "scripts" / name).write_text(text)
        (root / "mine" / d).mkdir(parents=True, exist_ok=True)
        (root / "mine" / d / name).write_text(text)
    for rel, text in own.items():
        p = root / rel
        p.mkdir(parents=True, exist_ok=True) if p.suffix == "" else p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    (root / "logs.txt").write_text("Action 1 | Step 0\n")
    return root


def test_own_scripts_are_the_written_and_the_edited(tmp_path: Path):
    shipped = {"shaft_down.py": "def shaft_down(): pass\n", "fell.py": "def fell(): pass\n"}
    life = _fake_life(tmp_path / "m", {
        "mine/procedures/fast_tunnel.py": "def fast_tunnel(): pass\n",
        "mine/reflexes/fell.py": "def fell(): return 'edited'\n",
        "mine/tools/orescan.py": "print()\n",
        "mine/notes.md": "diary\n",
    }, shipped)
    assert memory_at.own_files(life) == {"procedures/fast_tunnel.py": "written",
                                         "reflexes/fell.py": "edited",
                                         "tools/orescan.py": "written"}


def test_strip_own_keeps_the_diary_in_every_life_and_drops_the_scripts(tmp_path: Path):
    shipped = {"shaft_down.py": "def shaft_down(): pass\n", "fell.py": "def fell(): pass\n"}
    seed = _fake_life(tmp_path / "life2", {
        "mine/procedures/bore.py": "x\n", "mine/reflexes/fell.py": "edited\n",
        "mine/working.md": "life 2 diary\n", "mine/looks/a.png": "png",
    }, shipped)
    _fake_life(seed / "previous" / "life_1", {
        "mine/tools/orescan.py": "y\n", "mine/notes.md": "life 1 diary\n",
    }, shipped)
    out = tmp_path / "stripped"
    info = memory_at.strip_own(seed, out)

    assert info["lives"] == {"previous/life_1": {"tools/orescan.py": "written"},
                             ".": {"procedures/bore.py": "written", "reflexes/fell.py": "edited"}}
    assert not (out / "mine" / "procedures" / "bore.py").exists()
    assert (out / "mine" / "reflexes" / "fell.py").read_text() == shipped["fell.py"]
    assert (out / "mine" / "procedures" / "shaft_down.py").exists()
    assert (out / "mine" / "working.md").read_text() == "life 2 diary\n"
    assert (out / "mine" / "looks" / "a.png").exists()
    l1 = out / "previous" / "life_1"
    assert not (l1 / "mine" / "tools").exists()
    assert (l1 / "mine" / "notes.md").read_text() == "life 1 diary\n"
    assert (l1 / "logs.txt").exists() and (out / "logs.txt").exists()
    assert (out / ".strip.json").exists()
    # the stripped copy brings the same lives, in the same order, and holds no script of its own
    assert [p.relative_to(out) for p in memory_at.lives_of(out)] \
        == [p.relative_to(seed) for p in memory_at.lives_of(seed)]
    assert all(memory_at.own_files(life) == {} for life in memory_at.lives_of(out))
    with pytest.raises(SystemExit):
        memory_at.strip_own(seed, out)


def test_the_tail_tasks_start_from_the_same_kit_and_end_apart():
    import yaml
    from task_milestones import load_milestone_cfg
    chains = {t: [c["identity"] for c in load_milestone_cfg(t)] for t in TAIL_TASKS}
    assert all(chain[:3] == ["furnace", "mine_iron_ore", "iron_ingot"] for chain in chains.values())
    assert len({chain[-1] for chain in chains.values()}) == 3
    diamond = {c["identity"] for c in load_milestone_cfg("mine_diamond_from_scratch")}
    assert all(chain[-1] not in diamond for chain in chains.values())
    kits, texts = set(), {}
    for t in TAIL_TASKS:
        cfg = yaml.safe_load((MCU / "MCU_benchmark" / "task_configs" / "tasks" / t / f"{t}.yaml").read_text())
        kits.add(tuple(cfg["custom_init_commands"]))
        texts[t] = cfg["text"]
        assert cfg["world_seed"] == 1
    assert len(kits) == 1 and any("stone_pickaxe" in c for c in next(iter(kits)))
    # the task text tells the model what it starts with and what it is for
    assert all("stone pickaxe" in s and "crafting table" in s for s in texts.values())
    assert all(chains[t][-1].replace("_", " ") in texts[t].lower() for t in TAIL_TASKS)
    agent_src = (MCU / "src" / "agent.py").read_text()
    assert all(agent_src.count(f'"{t}"') == 2 for t in TAIL_TASKS)   # valid_categories + LONG_TASKS


# ---- --install-carried: the carried lives' own scripts are put in mine/ -------------

#: A procedure an earlier life wrote: one raw step forward, in the actions.json shape.
WALK = ('"""walk: one step forward (an earlier life\'s own procedure)."""\n'
        'import json\nprint(json.dumps({"actions": [{"action": {"forward": 1}, "repeat": 2}]}))\n')


def _seed_life(d: Path, log: str, mine: dict[str, str], shipped: dict[str, str]) -> Path:
    """A carried life on disk: its log, its shipped examples under skills/, its mine/."""
    (d / "logs.txt").parent.mkdir(parents=True, exist_ok=True)
    (d / "logs.txt").write_text(log)
    for rel, text in shipped.items():
        (d / "skills" / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / "skills" / rel).write_text(text)
    for rel, text in mine.items():
        (d / "mine" / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / "mine" / rel).write_text(text)
    return d


def test_install_takes_what_the_lives_wrote_and_the_newest_life_wins(tmp_path: Path):
    from mcu_worldmodel.previous import PreviousLives, installed_note
    shipped = {"procedures/scripts/shaft_down.py": "SHIPPED\n",
               "reflexes/scripts/hit.py": "SHIPPED HIT\n"}
    l1 = _seed_life(tmp_path / "l1", "Action 0 | Step 0 | one\n", {
        "procedures/walk.py": "v1\n", "procedures/shaft_down.py": "SHIPPED\n",
        "tools/scan.py": "scan\n", "notes.md": "diary\n"}, shipped)
    # life 2 carried life 1 and rewrote walk, edited the hit example
    l2 = _seed_life(tmp_path / "l2", "Action 0 | Step 0 | two\n", {
        "procedures/walk.py": "v2\n", "reflexes/hit.py": "EDITED HIT\n"}, shipped)
    _seed_life(l2 / "previous" / "life_1", "Action 0 | Step 0 | one\n", {
        "procedures/walk.py": "v1\n", "tools/scan.py": "scan\n"}, shipped)

    root = tmp_path / "probe"
    prev = PreviousLives(root)
    prev.seed([l2])
    rows = prev.install_own()

    assert rows == [{"path": "mine/procedures/walk.py", "life": 2, "kind": "written"},
                    {"path": "mine/reflexes/hit.py", "life": 2, "kind": "edited"},
                    {"path": "mine/tools/scan.py", "life": 1, "kind": "written"}]
    assert (root / "mine" / "procedures" / "walk.py").read_text() == "v2\n"
    assert not (root / "mine" / "procedures" / "shaft_down.py").exists()   # an unchanged example
    assert not (root / "mine" / "notes.md").exists()                        # the diary stays in previous/
    # a copy, not a link: editing the installed script never edits the carried record
    (root / "mine" / "procedures" / "walk.py").write_text("fixed\n")
    assert (root / "previous" / "life_2" / "mine" / "procedures" / "walk.py").read_text() == "v2\n"
    note = installed_note(rows)
    assert "`mine/procedures/walk.py` (life 2, its own script)" in note
    assert "`mine/reflexes/hit.py` (life 2, an example it edited)" in note
    assert "none:" in installed_note([])

    # the diary-only seed (memory_at --strip-own) installs nothing
    stripped = tmp_path / "stripped"
    memory_at.strip_own(l2, stripped)
    p2 = PreviousLives(tmp_path / "probe2")
    p2.seed([stripped])
    assert p2.install_own() == []


def test_an_installed_procedure_is_called_by_name_in_the_next_life(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    l1 = agent.memory.root
    (l1 / "mine" / "procedures").mkdir(parents=True, exist_ok=True)
    (l1 / "mine" / "procedures" / "walk.py").write_text(WALK)

    script = [{"actions": {"actions": [{"procedure": "walk", "args": {}}]},
               "message": "[PLAN]\nuse the installed walk"}] * 24
    agent, _ = drive_chassis(tmp_path / "life_2", "mfm", script=script,
                             previous_lives=[str(l1)], carried_world="other",
                             install_carried=True, **_arm("mfm"))
    root = agent.memory.root
    assert (root / "mine" / "procedures" / "walk.py").read_text() == WALK
    assert agent.installed == [{"path": "mine/procedures/walk.py", "life": 1, "kind": "written"}]
    assert agent._own_calls.get("walk", 0) >= 1                       # it ran, uncopied

    contract = (root / "AGENTS.md").read_text()
    assert "[INSTALLED]" in contract and "`mine/procedures/walk.py` (life 1, its own script)" in contract
    procs = (root / "skills" / "procedures" / "SKILL.md").read_text()
    assert "already installed in `mine/procedures/`" in procs and "not copied for you" not in procs
    mem = (root / "skills" / "memory" / "SKILL.md").read_text()
    assert "installed for you in `mine/`" in mem and "copy the scripts worth keeping" not in mem
    assert agent.report()["installed"] == agent.installed


def test_without_install_the_carried_life_is_as_shipped(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    l1 = agent.memory.root
    (l1 / "mine" / "procedures").mkdir(parents=True, exist_ok=True)
    (l1 / "mine" / "procedures" / "walk.py").write_text(WALK)
    agent, _ = drive_chassis(tmp_path / "life_2", "mfm", previous_lives=[str(l1)],
                             carried_world="other", **_arm("mfm"))
    root = agent.memory.root
    assert not (root / "mine" / "procedures" / "walk.py").exists()
    assert "[INSTALLED]" not in (root / "AGENTS.md").read_text()
    assert "not copied for you" in (root / "skills" / "procedures" / "SKILL.md").read_text()
    assert agent.installed == []


def test_install_needs_carried_lives_on_the_mfm_arm(tmp_path: Path):
    with pytest.raises(ValueError, match="install_carried"):
        drive_chassis(tmp_path, "mfm", install_carried=True, **_arm("mfm"))


def test_the_coal_and_meat_tails_start_from_the_iron_tails_kit():
    import yaml
    from task_milestones import load_milestone_cfg
    tasks = MCU / "MCU_benchmark" / "task_configs" / "tasks"
    kit = yaml.safe_load((tasks / "iron_shield_tail" / "iron_shield_tail.yaml").read_text())["custom_init_commands"]
    coal = yaml.safe_load((tasks / "coal_torches_tail" / "coal_torches_tail.yaml").read_text())
    meat = yaml.safe_load((tasks / "cook_meat_tail" / "cook_meat_tail.yaml").read_text())
    assert coal["custom_init_commands"] == kit
    # the meat tail adds its animals to the same kit, and says so in the task text
    assert meat["custom_init_commands"][:len(kit)] == kit
    extra = meat["custom_init_commands"][len(kit):]
    assert len(extra) == 3 and all(c.startswith("/summon minecraft:cow ") for c in extra)
    assert "three cows" in meat["text"] and "stone pickaxe" in coal["text"]
    assert coal["world_seed"] == meat["world_seed"] == 1
    assert [c["identity"] for c in load_milestone_cfg("coal_torches_tail")] == ["mine_coal_ore", "torch"]
    assert [c["identity"] for c in load_milestone_cfg("cook_meat_tail")] \
        == ["furnace", "kill_animal", "cooked_meat"]
    # the same rules as the from-scratch tasks they are the tails of
    for tail, whole in (("coal_torches_tail", "coal_torches"), ("cook_meat_tail", "cook_meat")):
        rules = {c["identity"]: c for c in load_milestone_cfg(whole)}
        assert all(rules[c["identity"]] == c for c in load_milestone_cfg(tail))
    agent_src = (MCU / "src" / "agent.py").read_text()
    assert all(agent_src.count(f'"{t}"') == 2 for t in ("coal_torches_tail", "cook_meat_tail"))


# ---- --install-scripts: the scripts alone, nothing else of the earlier lives ---------

def test_install_scripts_gives_the_scripts_and_no_record(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    l1 = agent.memory.root
    (l1 / "mine" / "procedures").mkdir(parents=True, exist_ok=True)
    (l1 / "mine" / "procedures" / "walk.py").write_text(WALK)
    (l1 / "mine" / "notes.md").write_text("the diary of life 1\n")

    script = [{"actions": {"actions": [{"procedure": "walk", "args": {}}]},
               "message": "[PLAN]\nuse the installed walk"}] * 24
    agent, _ = drive_chassis(tmp_path / "life_2", "mfm", script=script,
                             install_scripts=[str(l1)], **_arm("mfm"))
    root = agent.memory.root
    assert (root / "mine" / "procedures" / "walk.py").read_text() == WALK
    assert agent._own_calls.get("walk", 0) >= 1
    # nothing else of life 1: no previous/, no diary, no carried index
    assert not (root / "previous").exists()
    assert not any("the diary of life 1" in p.read_text(errors="replace")
                   for p in root.rglob("*.md"))
    contract = (root / "AGENTS.md").read_text()
    assert "[INSTALLED]" in contract and "`mine/procedures/walk.py` (life 1, its own script)" in contract
    assert "ALL that is here" in contract and "previous/life_<i>/" not in contract
    rep = agent.report()
    assert rep["installed"] == agent.installed and rep["install_scripts"] == [str(l1)]
    assert "carried_world" not in rep

    # apart from the installed scripts and what names them, the workspace is the
    # no-memory life's: same files at the start, same contract but for the note
    bare, _ = drive_chassis(tmp_path / "life_3", "mfm", script=script, **_arm("mfm"))
    bare_contract = (bare.memory.root / "AGENTS.md").read_text()
    assert contract.startswith(bare_contract.rstrip())
    assert contract[len(bare_contract.rstrip()):].lstrip().startswith("[INSTALLED]")


def test_install_scripts_is_not_a_carry(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    l1 = str(agent.memory.root)
    with pytest.raises(ValueError, match="install_scripts"):
        drive_chassis(tmp_path / "x", "mfm", previous_lives=[l1], install_scripts=[l1],
                      **_arm("mfm"))
    with pytest.raises(ValueError, match="install_scripts"):
        drive_chassis(tmp_path / "y", "logbook", install_scripts=[l1], **_arm("logbook"))


@pytest.mark.parametrize("vein, tail, ore", [("iron_shield_vein", "iron_shield_tail", "iron_ore"),
                                             ("coal_torches_vein", "coal_torches_tail", "coal_ore")])
def test_the_placed_vein_is_where_the_task_text_says(vein: str, tail: str, ore: str):
    """The vein tasks: the fill is relative to the spawn, the text is in world
    coordinates; they must name the same eight blocks."""
    import math
    import yaml
    from task_milestones import load_milestone_cfg
    tasks = MCU / "MCU_benchmark" / "task_configs" / "tasks"
    cfg = yaml.safe_load((tasks / vein / f"{vein}.yaml").read_text())
    tail_cfg = yaml.safe_load((tasks / tail / f"{tail}.yaml").read_text())
    kit, fill = cfg["custom_init_commands"][:-1], cfg["custom_init_commands"][-1]
    assert kit == tail_cfg["custom_init_commands"]
    assert load_milestone_cfg(vein) == load_milestone_cfg(tail)
    m = re.fullmatch(r"/execute as @p at @s run fill ~(-?\d+) ~(-?\d+) ~(-?\d+) ~(-?\d+) ~(-?\d+) "
                     r"~(-?\d+) minecraft:" + ore + r" replace", fill)
    assert m
    dx0, dy0, dz0, dx1, dy1, dz1 = (int(v) for v in m.groups())
    spawn = (-5853.5, 68.0, -3781.5)                     # every probe life of world seed 1
    block = lambda v, d: math.floor(v + d)               # noqa: E731
    xs = sorted((block(spawn[0], dx0), block(spawn[0], dx1)))
    ys = sorted((block(spawn[1], dy0), block(spawn[1], dy1)))
    zs = sorted((block(spawn[2], dz0), block(spawn[2], dz1)))
    assert f"x {xs[0]} to {xs[1]}, y {ys[0]} to {ys[1]}, z {zs[0]} to {zs[1]}" in cfg["text"]
    assert (xs[1] - xs[0] + 1) * (ys[1] - ys[0] + 1) * (zs[1] - zs[0] + 1) == 8
    # straight down the spawn column, then south: the vein is on that line
    assert xs[0] <= math.floor(spawn[0]) <= xs[1]
    assert f"{int(spawn[1]) - ys[0]} blocks below" in cfg["text"]
    assert f"{zs[0] - math.floor(spawn[2])} blocks south" in cfg["text"]
    agent_src = (MCU / "src" / "agent.py").read_text()
    assert agent_src.count(f'"{vein}"') == 2


# ---- the endgame skill probes (third design, slurm/skill_reuse3.sbatch) -----------------

ENDGAME_TAILS = ("blaze_tail", "enderman_tail", "eye_craft_tail", "end_stone_tail", "dragon_tail")


def _contract(agent) -> str:
    ws = agent.memory.root
    return next(ws / n for n in ("CLAUDE.md", "AGENTS.md") if (ws / n).exists()).read_text()


def test_a_granted_macro_joins_the_atoms_and_a_withheld_one_is_refused(tmp_path: Path):
    from mcu_worldmodel import procedures as P
    base, _ = drive_chassis(tmp_path / "base", "mfm", **_arm("mfm"))
    assert "fight_blaze" not in P.visible_names() and "fight" not in P.visible_names()
    assert "fight_blaze" not in _contract(base)
    script = [{"actions": {"actions": [{"procedure": "fight_blaze", "args": {}}]},
               "message": "[PLAN]\nfight"},
              {"actions": {"actions": [{"procedure": "fight", "args": {}}]},
               "message": "[PLAN]\nfight again"},
              {"actions": {"actions": [{"procedure": "explore_nether", "args": {}}]},
               "message": "[PLAN]\nwalk"}] + [
              {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
               "message": "[PLAN]\nchop"}] * 20
    agent, _ = drive_chassis(tmp_path / "row", "mfm", script=script,
                             grant=["fight", "fight_blaze", "face_entity"], withhold=["fight_blaze"],
                             **_arm("mfm"))
    assert "fight" in P.visible_names() and "fight_blaze" not in P.visible_names()
    assert "fight_blaze" in P.WITHHELD
    log = (agent.memory.root / "logs.txt").read_text()
    assert "'fight_blaze' is withheld in this run" in log
    assert "'explore_nether' is not in this run's procedure set (the atoms)" in log
    assert "'fight' is withheld" not in log and "'fight' is not in this run's" not in log
    contract = _contract(agent)
    assert "fight_blaze" not in contract and "face_entity" in contract
    # the atoms head of the situations reference says what the row built in all the same
    skills = (agent.memory.root / "references" / "skills.md").read_text()
    assert "Built in for this run all the same" in skills and "face_entity, fight" in skills
    rep = agent.report()
    assert rep["granted"] == ["face_entity", "fight", "fight_blaze"] and rep["withheld"] == ["fight_blaze"]
    assert "granted" not in base.report() and "withheld" not in base.report()


def test_an_unknown_grant_is_a_launch_error(tmp_path: Path):
    with pytest.raises(ValueError, match="grant names no procedure"):
        drive_chassis(tmp_path, "mfm", grant=["fight_dragon"], **_arm("mfm"))
    with pytest.raises(ValueError, match="withhold names no procedure"):
        drive_chassis(tmp_path, "mfm", withhold=["fight_dragon"], **_arm("mfm"))
    with pytest.raises(ValueError, match="start_dimension"):
        drive_chassis(tmp_path, "mfm", start_dimension="moon", **_arm("mfm"))


def test_the_endgame_recipes_say_which_macros_the_row_built_in(tmp_path: Path):
    from mcu_worldmodel import prompts
    agent, _ = drive_chassis(tmp_path / "recipe", "mfm", endgame_recipes=True, **_arm("mfm"))
    ref = agent.memory.root / "references" / "endgame.md"
    assert ref.exists()
    text = ref.read_text()
    head = text.split("\n")[0]
    assert head.startswith("The macros this file names that are NOT built in this run -- ")
    # the atoms the recipes name (pillar_up, look_abs, ...) are built in; the macros are not
    recipes, _, built = head.partition("Built in for this run")
    assert "fight_blaze" in recipes and "enderman_pit" in recipes and "throw_eye" in recipes
    assert "pillar_up" in built and "fight_blaze" not in built
    assert prompts.ENDGAME_RECIPES.strip() in text
    assert "`references/endgame.md`" in _contract(agent)
    assert agent.report()["endgame_recipes"] is True
    both, _ = drive_chassis(tmp_path / "both", "mfm", endgame_recipes=True,
                            grant=["fight", "fight_blaze"], **_arm("mfm"))
    head = (both.memory.root / "references" / "endgame.md").read_text().split("\n")[0]
    recipes, _, built = head.partition("Built in for this run")
    assert "fight_blaze" in built and "fight_blaze" not in recipes
    assert "enderman_pit" in recipes and "enderman_pit" not in built
    plain, _ = drive_chassis(tmp_path / "plain", "mfm", **_arm("mfm"))
    assert not (plain.memory.root / "references" / "endgame.md").exists()
    assert "endgame.md" not in _contract(plain)


def test_start_dimension_tells_the_harness_where_the_config_put_it(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "end", "mfm", start_dimension="end", **_arm("mfm"))
    assert agent._dimension == "the End"
    assert agent.report()["start_dimension"] == "the End"
    plain, _ = drive_chassis(tmp_path / "plain", "mfm", **_arm("mfm"))
    assert plain._dimension == "the Overworld"
    assert "start_dimension" not in plain.report()


def test_the_endgame_tails_are_the_dragon_chains_last_eight_with_the_search_handed_over():
    import yaml
    from task_milestones import load_milestone_cfg
    dragon = load_milestone_cfg("ender_dragon")
    last_eight = [c["identity"] for c in dragon[16:]]
    assert last_eight == ["kill_blaze", "blaze_rod", "kill_enderman", "ender_pearl", "blaze_powder",
                          "eye_of_ender", "end_stone", "kill_ender_dragon"]
    rule_of = {c["identity"]: (c["event"], tuple(c["objects"])) for c in dragon}
    probed: set[str] = set()
    tasks = MCU / "MCU_benchmark" / "task_configs" / "tasks"
    agent_src = (MCU / "src" / "agent.py").read_text()
    for t in ENDGAME_TAILS:
        cfg = yaml.safe_load((tasks / t / f"{t}.yaml").read_text())
        chain = load_milestone_cfg(t)
        for c in chain:
            # the dragon config's own rule, event and objects alike
            assert rule_of[c["identity"]] == (c["event"], tuple(c["objects"])), (t, c["identity"])
            probed.add(c["identity"])
        assert cfg["world_seed"] == 0                       # the dragon world
        cmds = cfg["custom_init_commands"]
        assert "credited" in cfg["text"]
        assert agent_src.count(f'"{t}"') == 2               # valid_categories + LONG_TASKS
        if t in ("end_stone_tail", "dragon_tail"):
            tp = next(i for i, c in enumerate(cmds) if "run tp @s 100 49 0" in c)
            fills = [i for i, c in enumerate(cmds) if "run fill 98 48 -2 102 48 2 minecraft:obsidian" in c]
            assert fills and fills[0] < tp                  # the platform stands before the jump
            assert all("minecraft:the_end" in c for c in cmds if "execute in" in c)
        else:
            assert not any("execute in" in c for c in cmds)
        if t in ("blaze_tail", "enderman_tail"):
            mob = "blaze" if t == "blaze_tail" else "enderman"
            # plain summons: an NBT suffix was dropped on the chat path (smoke 50211411)
            assert sum(f"summon minecraft:{mob} " in c for c in cmds) == 3
            assert not any("{" in c for c in cmds)
    assert probed == set(last_eight)


def test_the_third_launcher_grants_what_the_table_counts():
    import re as _re
    from skill_reuse3_table import MACROS, ROWS, TASKS
    launcher = (MCU / "slurm" / "skill_reuse3.sbatch").read_text()
    fight = _re.search(r'GRANT_FIGHT="\$\{GRANT_FIGHT:-([a-z_,]+)\}"', launcher).group(1).split(",")
    macros = _re.search(r'GRANT_MACROS="\$\{GRANT_MACROS:-\$GRANT_FIGHT,([a-z_,]+)\}"', launcher).group(1).split(",")
    assert set(fight) | set(macros) == set(MACROS)
    from mcu_worldmodel import procedures as P
    assert all(n in P.REGISTRY for n in MACROS) and not any(n in P.ATOMS for n in MACROS)
    assert all(t in launcher for t in TASKS)
    # every row the table knows is a case of the launcher (carry3.. share one glob case)
    assert all(f"{r})" in launcher or (r.startswith("carry") and "carry[3-9])" in launcher)
               for r in ROWS)
    for name in ("kill", "end", "cow", "raw", "loop"):
        lines = (MCU / "slurm" / "smoke" / f"{name}.jsonl").read_text().splitlines()
        written: set[str] = set()                      # scripts the fake wrote this life
        for line in lines:
            step = json.loads(line)
            written |= {Path(f).stem for f in (step.get("files") or {})
                        if f.startswith("mine/procedures/")}
            assert all(a["procedure"] in P.REGISTRY or a["procedure"] in written
                       for a in step["artifact"]["actions"] if "procedure" in a)
            assert all(set(a) <= {"action", "repeat"} for a in step["artifact"]["actions"]
                       if "procedure" not in a)


def test_a_sword_use_beside_a_block_break_is_not_a_hit():
    from skill_reuse3_table import entity_hits
    log = "\n".join([
        "[EVENT] mine_block spruce_log +1",
        "[EVENT] use_item wooden_sword +1",          # the sword broke the log
        "[STATE] pos=(1, 2, 3)",
        "[EVENT] use_item diamond_sword +1",         # a hit
        "[EVENT] use_item diamond_sword +1",         # a hit
        "[EVENT] kill_entity blaze +1",
        "[PLAN] it quotes [EVENT] use_item diamond_sword in its own text",
        "[EVENT] use_item diamond_sword +1",
        "[EVENT] mine_block fern +1",                 # the sword cut a fern
    ])
    assert entity_hits(log) == 2
