"""Pins of the Minecraft arms under the settings of `mcu_worldmodel.arms`.

Each arm is driven through the chassis with the scripted model of `test_pins_chassis`
and everything it shows the model or writes beside it is pinned: the contract, every
turn prompt, the log, the episode index, the actions returned to the driver, and a
sha256 manifest of the whole workspace (references/, skills/, tools/, episodes/).

    mfm          the self-writing arm: from scratch, with a carried life, and on the
                 Claude Code channel
    mfm-matched  the same memory on the baselines' contract: from scratch and with a
                 carried life
    logbook      PRO-LONG's protocol on the same chassis
    direct       no persistent memory
    vista        the contract alone; the app-server thread is pinned in `test_vista.py`

Every arm reads a short contract, has the 28 atoms as its procedure set and runs
without the runner's guards.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from conftest import ROOT, check_pin
from test_pins_chassis import _norm, drive_chassis
from test_vista import drive_vista_chassis, fake_appserver  # noqa: F401

PINS = "../pins_release/"
FRAME_SIZE = (320, 180)
def _arm(name: str) -> dict:
    from mcu_worldmodel.arms import ARMS
    return dict(ARMS[name], frame_size=FRAME_SIZE)


def _manifest(ws: Path, tmp: Path) -> str:
    rows = []
    for p in sorted(ws.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        data = p.read_bytes()
        if p.suffix in (".md", ".txt", ".py", ".json", ".jsonl"):
            data = _norm(data.decode("utf-8", "replace"), tmp).encode()
        rows.append(f"{hashlib.sha256(data).hexdigest()}  {p.relative_to(ws).as_posix()}")
    return "\n".join(rows) + "\n"


def _pin_arm(name: str, agent, actions, tmp: Path) -> None:
    ws = agent.memory.root
    # CLAUDE.md is the contract on the Claude Code channel, AGENTS.md on codex
    contract = next(ws / n for n in ("CLAUDE.md", "AGENTS.md") if (ws / n).exists())
    check_pin(f"{PINS}{name}_contract.md", _norm(contract.read_text(), tmp))
    # every prompt by hash, the first and the last in full
    prompts = [_norm(p, tmp) for p in agent.codex.prompts]
    check_pin(f"{PINS}{name}_prompts.txt",
              "\n".join(hashlib.sha256(p.encode()).hexdigest() for p in prompts)
              + "\n=====\n" + prompts[0] + "\n=====\n" + prompts[-1])
    check_pin(f"{PINS}{name}_actions.json",
              json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v)
                           for k, v in a.items()} for a in actions], sort_keys=True))
    if (ws / "logs.txt").exists():
        check_pin(f"{PINS}{name}_logs.txt", _norm((ws / "logs.txt").read_text(), tmp))
    if (ws / "index.jsonl").exists():
        check_pin(f"{PINS}{name}_index.jsonl", _norm((ws / "index.jsonl").read_text(), tmp))
    check_pin(f"{PINS}{name}_workspace.txt", _manifest(ws, tmp))


def test_mfm_from_scratch(tmp_path: Path):
    agent, actions = drive_chassis(tmp_path, "mfm", **_arm("mfm"))
    _pin_arm("mfm", agent, actions, tmp_path)


def test_mfm_with_a_carried_life(tmp_path: Path):
    first, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm"))
    agent, actions = drive_chassis(tmp_path / "life_2", "mfm",
                                   previous_lives=[str(first.memory.root)], **_arm("mfm"))
    _pin_arm("mfm_carried", agent, actions, tmp_path)


def test_mfm_on_claude_code(tmp_path: Path):
    agent, actions = drive_chassis(tmp_path, "mfm", cli="claude", **_arm("mfm"))
    _pin_arm("mfm_claude", agent, actions, tmp_path)


def test_mfm_matched_from_scratch(tmp_path: Path):
    agent, actions = drive_chassis(tmp_path, "mfm", **_arm("mfm-matched"))
    _pin_arm("mfm_matched", agent, actions, tmp_path)


def test_mfm_matched_with_a_carried_life(tmp_path: Path):
    first, _ = drive_chassis(tmp_path / "life_1", "mfm", **_arm("mfm-matched"))
    agent, actions = drive_chassis(tmp_path / "life_2", "mfm",
                                   previous_lives=[str(first.memory.root)],
                                   **_arm("mfm-matched"))
    _pin_arm("mfm_matched_carried", agent, actions, tmp_path)


def test_the_two_mfm_arms_differ_in_the_harness_only():
    from mcu_worldmodel.arms import ARMS, MEMORY_MODE, MFM_MEMORY, MFM_OWN, SHARED
    assert MEMORY_MODE["mfm"] == MEMORY_MODE["mfm-matched"] == "mfm"
    assert ARMS["logbook"] == ARMS["direct"] == ARMS["vista"] == SHARED
    assert ARMS["mfm-matched"] == {**SHARED, **MFM_MEMORY}
    assert ARMS["mfm"] == {**SHARED, **MFM_MEMORY, **MFM_OWN}
    assert not set(SHARED) & set(MFM_MEMORY) and not set(MFM_MEMORY) & set(MFM_OWN)


@pytest.mark.parametrize("mode", ["logbook", "direct"])
def test_baseline_arm(tmp_path: Path, mode: str):
    agent, actions = drive_chassis(tmp_path, mode, **_arm(mode))
    _pin_arm(mode, agent, actions, tmp_path)


def test_vista_arm_contract(tmp_path: Path, fake_appserver):  # noqa: F811
    from mcu_worldmodel.arms import ARMS
    agent, _ = drive_vista_chassis(tmp_path, fake_appserver, steps=40, arm=ARMS["vista"])
    check_pin(f"{PINS}vista_contract.md",
              _norm((agent.memory.root / "AGENTS.md").read_text(), tmp_path))


@pytest.mark.parametrize("name", ["direct", "logbook", "vista", "mfm-matched", "mfm"])
def test_every_arm_has_the_atoms_and_a_short_contract(tmp_path: Path, name: str,
                                                      fake_appserver):  # noqa: F811
    """No arm is given a macro, none is pointed at a file it cannot read, and only the
    arm that keeps procedures of its own is told to write one."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.arms import ARMS, MEMORY_MODE
    mode = MEMORY_MODE[name]
    if mode == "vista":
        agent, _ = drive_vista_chassis(tmp_path, fake_appserver, steps=20, arm=ARMS[name])
    else:
        agent, _ = drive_chassis(tmp_path, mode, steps=20, **_arm(name))
    ws = agent.memory.root
    contract = (ws / "AGENTS.md").read_text()
    assert len(contract.encode()) < 20_000
    macros = set(P.REGISTRY) - set(P.ATOMS) - {"fight"}       # a word of the text
    named = set(re.findall(r"[a-z_]+", contract)) & macros
    assert not named, named
    table = contract[contract.index("**Procedures**"):].split("procedure set is the ATOMS")[0]
    listed = {ln.split("(")[0].strip("-` ") for ln in table.splitlines() if ln.startswith("- `")}
    assert listed == set(P.ATOMS)
    note = P.expand("dig_down", {"n": 4})[1]
    assert "not in this run's procedure set" in note
    assert ("mine/procedures" in note) == (name == "mfm")
    assert ("your own procedure" in contract) == (name == "mfm")
    assert (ws / "references").is_dir() == (mode not in ("direct", "vista"))
    assert ("references/" in contract) == (mode not in ("direct", "vista"))
    # what describes the atoms and the screens names no procedure outside the atoms
    for ref in ("procedures.md", "gui.md"):
        if (ws / "references" / ref).exists():
            text = (ws / "references" / ref).read_text()
            for gone in ("aim_at_ore", "cursor_to", "use_until_gui", "face_entity"):
                assert not re.search(rf"\b{gone}\b(?!_)", text), (ref, gone)
    # the runner guards no arm, and says so; the reflexes are the self-writing arm's
    assert agent.reflexes is False
    assert "The runner does not guard you in this run" in contract
    told = contract + "".join(p.read_text() for p in sorted(ws.glob("references/*.md")))
    assert ("mine/reflexes" in told) == (name == "mfm")
    assert "the runner interrupts your plan" not in told


def test_release_pins_are_under_the_repo():
    assert (ROOT / "tests" / "pins_release").is_dir()
