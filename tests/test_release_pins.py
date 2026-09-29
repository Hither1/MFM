"""Pins of the four Minecraft arms under the settings the paper's runs used.

Each arm is driven through the chassis with the scripted model of `test_pins_chassis`
and everything it shows the model or writes beside it is pinned: the contract, every
turn prompt, the log, the episode index, the actions returned to the driver, and a
sha256 manifest of the whole workspace (references/, skills/, tools/, episodes/).

    mfm      as `mcu_worldmodel.arms` defines it: from scratch, with a carried life,
             and on the Claude Code channel
    logbook  PRO-LONG's protocol on the same chassis
    direct   no persistent memory

The VISTA arm runs through the app-server thread and is pinned in `test_vista.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import ROOT, check_pin
from test_pins_chassis import _norm, drive_chassis

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


@pytest.mark.parametrize("mode", ["logbook", "direct"])
def test_baseline_arm(tmp_path: Path, mode: str):
    agent, actions = drive_chassis(tmp_path, mode, **_arm(mode))
    _pin_arm(mode, agent, actions, tmp_path)


def test_release_pins_are_under_the_repo():
    assert (ROOT / "tests" / "pins_release").is_dir()
