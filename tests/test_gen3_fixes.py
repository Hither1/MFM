"""Fixes after the gen-3 pre-launch review (2026-09-09): the codex skill catalog survives
the sweep by rule, the harness skill package is not carried under previous/, no earlier
life's outcome is in the model-facing text (rules only -- the model reads previous/ itself),
the per-arm codex home keeps codex's bundled skills out of the catalog, and the index row
carries the first note / the events so `--grep` and `--ores` read the index alone."""
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


def test_catalog_dir_survives_the_sweep(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory
    mem = MultimodalMemory(tmp_path / "m", structured=False, episodes=True, own=True)
    (mem.root / ".agents" / "skills").mkdir(parents=True)
    (mem.root / "then_now.png").write_bytes(b"x")
    removed = mem.sweep_foreign()
    assert "then_now.png" in removed and ".agents" not in removed
    assert (mem.root / ".agents" / "skills").is_dir()


def test_harness_skill_package_is_not_carried(tmp_path: Path):
    from test_previous import make_life
    from mcu_worldmodel.previous import NOT_CARRIED, PreviousLives
    assert "skills" in NOT_CARRIED
    gen1 = make_life(tmp_path, "gen1")
    (gen1 / "skills" / "memory").mkdir(parents=True)
    (gen1 / "skills" / "memory" / "SKILL.md").write_text("old doctrine")
    (gen1 / "mine" / "skills" / "portal_check").mkdir(parents=True)
    (gen1 / "mine" / "skills" / "portal_check" / "SKILL.md").write_text("the model's own")
    pl = PreviousLives(tmp_path / "gen2")
    pl.seed([gen1])
    life = tmp_path / "gen2" / "previous" / "life_1"
    assert not (life / "skills").exists()                                   # harness machinery
    assert (life / "mine" / "skills" / "portal_check" / "SKILL.md").exists()  # the life's own record


#: An earlier life's outcome, as the harness used to tell it: a run named, a step count,
#: "the N runs before this one", "one life spent ...", "every life so far".
ANECDOTE = re.compile(
    r"\b(og|of|hd|kd|lad|dm|obf?)\d+\b"
    r"|\d{1,3},\d{3} steps"
    r"|\bthe \d+ (runs|deaths|lives)\b"
    r"|\b(one|two|three|five|nine) (life|lives|run|runs) (spent|that|died|entered|rewrote|sat|lost)"
    r"|\b(previous|earlier) run (died|spent|sat|lost|cost)"
    r"|every (life|run) so far"
    r"|cost (an|a) (earlier|previous) run", re.I)


def _model_facing(tmp_path: Path) -> dict[str, str]:
    from mcu_worldmodel import prompts, skills as K
    from mcu_worldmodel import procedures as P
    P.set_visible(P.ATOMS)
    kw = dict(task_text="Kill the dragon", progress_block="0/24", entry_cap=40, step_cap=400,
              atoms=True, frames=True, harness_reflexes=False)
    texts = {"AGENTS.md": prompts.minimal_contract(previous=True, **kw)}
    full = prompts.act_prompt(task_text="Kill the dragon", progress_block="0/24", graph_summary="",
                              plan_summary="", discipline_summary="", entry_cap=40, step_cap=400,
                              memory_mode="mfm", retrieval=True, previous=True, expect=True,
                              frames=True, own=True, atoms=True, own_reflexes=True, harness_reflexes=False)
    P.set_visible(None)
    _, refs = prompts.thin_split(full)
    refs["skills.md"] = prompts.situations_atoms(refs["skills.md"])
    refs["survival.md"] = prompts.survival_atoms(refs["survival.md"])
    texts.update({f"references/{k}": v for k, v in refs.items()})
    from mcu_worldmodel import own as _own
    texts["references/own.md"] = _own.MFM_OWN_NOTE + _own.MFM_WORKING_NOTE + _own.reflex_note(False)
    K.write_skills(tmp_path)
    for p in sorted((tmp_path / "skills").rglob("*")):
        if p.is_file():
            texts[str(p.relative_to(tmp_path))] = p.read_text()
    return texts


def test_no_earlier_life_outcomes_in_the_model_facing_text(tmp_path: Path):
    """The user's rule (2026-09-09): what earlier lives did is for the model to read under
    previous/, not for the harness to tell. Rules stay; the lives' outcomes go."""
    hits = []
    for name, text in _model_facing(tmp_path).items():
        for m in ANECDOTE.finditer(text):
            hits.append(f"{name}: ...{text[max(0, m.start() - 40):m.end() + 40]!r}")
    assert not hits, "\n".join(hits)
    # the rules the review checked are still there
    mc = (tmp_path / "skills" / "minecraft" / "SKILL.md").read_text()
    assert "nearest water's edge" in mc and "18 or more" in mc and "4 wide x 5 tall" in mc
    mn = (tmp_path / "skills" / "mining" / "SKILL.md").read_text()
    assert "a dig, not a search" in mn and "Expose, then look, then break" in mn


def test_codex_home_blocks_the_bundled_skills(tmp_path: Path):
    """codex 0.153 installs its bundled skills into $CODEX_HOME/skills/.system at every
    start and lists them in the catalog (smoke 2026-09-09: a plain file at that path makes
    the install fail, logged and harmless, and the catalog holds the workspace's alone)."""
    auth = tmp_path / "auth.json"
    auth.write_text("{}")
    out = subprocess.run(["bash", str(MCU / "scripts" / "codex-home.sh"), "armx"], capture_output=True,
                         text=True, env={**os.environ, "MCU_CODEX_ROOT": str(tmp_path / "homes"),
                                         "MCU_CODEX_AUTH": str(auth)})
    assert out.returncode == 0, out.stderr
    home = tmp_path / "homes" / "armx"
    assert (home / "skills").is_dir() and (home / "skills" / ".system").is_file()
    assert f"CODEX_RUNTIME_HOME={home}" in out.stdout


def test_codex_env_puts_home_at_the_arm_home():
    src = (MCU / "mcu_worldmodel" / "codex_backend.py").read_text()
    assert 'env["HOME"] = str(self.codex_home)' in src        # $HOME/.agents/skills stays out of the catalog


def test_index_rows_carry_note_and_events_and_the_tool_reads_the_index(tmp_path: Path):
    from test_pins_chassis import drive_chassis
    from mfm.memory.tools import episodes as T
    script = [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
               "message": f"[PLAN]\nchop {i}\nEXPECT: a log"} for i in range(8)]
    agent, _ = drive_chassis(tmp_path, "mfm", steps=60, script=script)
    root = agent.memory.root
    rows = T.read_index(root)
    assert rows and all("events" in r for r in rows[1:])           # every closed entry says what it changed
    with_events = [r for r in rows if r.get("events")]
    assert with_events, [r.get("summary") for r in rows]
    noted = [r for r in rows if "note" in (r.get("tags") or [])]
    assert all(r.get("note") for r in noted)                         # a noted entry carries its first note
    # the index alone answers a grep and the ore question: hide the files and ask again
    (root / "episodes").rename(root / "episodes.hidden")
    needle = with_events[0]["events"][0].split()[1]
    assert any(r["id"] == with_events[0]["id"] for r in T.grep(rows, root, needle))
    ore_row = {**with_events[0], "events": ["mine_block iron_ore +1"], "inventory_delta": {"iron_ore": 1}}
    assert T.ore_hits(root, ore_row) == ["mine_block iron_ore +1"]
    # an old-format row (no `events` key) opens outcome.json only where an ore could be
    old = {k: v for k, v in with_events[0].items() if k not in ("events", "note", "inventory_delta")}
    assert T.ore_hits(root, {**old, "tags": ["stuck"], "summary": "moved 0.0"}) == []
    assert T.grep([old], root, "zzz-not-there") == []


def test_carry_enriches_an_old_lifes_rows_with_their_outcome(tmp_path: Path):
    """A seed recorded before the index carried note/events gets them at seed time, so
    `--grep`/`--ores` over previous/ read the index alone."""
    from test_previous import make_life
    from mcu_worldmodel.previous import PreviousLives
    from mfm.memory.tools import episodes as T
    gen1 = make_life(tmp_path, "gen1")
    (gen1 / "episodes" / "ep_000001" / "outcome.json").write_text(json.dumps({
        "events": ["mine_block iron_ore +1", "MILESTONE mine_iron_ore verified"],
        "notes": ["the runner stopped: iron-ore-like speckles.", "second note"],
        "inventory_delta": {"iron_ore": 1}}))
    ws = tmp_path / "gen2"
    PreviousLives(ws).seed([gen1])
    rows = T.read_index(ws, previous=True)
    assert rows[0]["events"] == ["mine_block iron_ore +1", "MILESTONE mine_iron_ore verified"]
    assert rows[0]["note"] == "the runner stopped: iron-ore-like speckles."
    assert rows[0]["inventory_delta"] == {"iron_ore": 1}
    (ws / "previous" / "life_1" / "episodes").rename(ws / "previous" / "life_1" / "gone")   # index only
    assert T.ore_hits(ws, rows[0]) == ["mine_block iron_ore +1"]
    assert T.grep(rows, ws, "speckles") == rows
