"""Pins of the KiCad memory arms under the settings the paper's runs used.

    prolong-logonly  PRO-LONG: the append-only log is the only memory
    mfm              MFM without cross-task memory (design turn, conventions)
    mfm-carry        MFM: the same, with the finished tasks' records carried

Each is replayed with the scripted episode of `test_pins_replay` on both CLI channels
and everything the model is shown or the driver gets back is pinned. The direct arm
and VISTA are pinned in `test_claude_kicad.py` and `test_vista.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from test_pins_replay import _dump_calls, _norm, drive_kicad

from conftest import check_pin

PINS = "../pins_release/kicad_"
DESIGN = dict(design=True, design_effort="high", conventions=True)
ARMS = {
    "prolong-logonly": {},
    "mfm": DESIGN,
    "mfm-carry": dict(DESIGN, carry_outcomes=True),
}
INTENT = {"parts": [{"ref": "R1", "symbol": "Device:R", "value": "10k"}],
          "nets": [{"label": "GND", "pins": ["R1.2"]}]}


def _manifest(root: Path, tmp: Path) -> str:
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        data = p.read_bytes()
        if p.suffix in (".md", ".txt", ".py", ".json", ".jsonl"):
            data = _norm(data.decode("utf-8", "replace"), tmp).encode()
        rows.append(f"{hashlib.sha256(data).hexdigest()}  {p.relative_to(root).as_posix()}")
    return "\n".join(rows) + "\n"


def _episode(kind: str, cli: str, task: str, tmp: Path, fake_codex):
    from gym_codex import memory_agents
    kw = dict(ARMS[kind])
    if kind.endswith("-carry"):
        kw.update(carry_dir=tmp / "out" / "carry", task_id=task)
    if cli == "claude":
        kw["cli"] = "claude"
    agent = memory_agents.make_agent(
        kind, workspace=tmp / "out" / task / "workspace", model="gpt-6-astra", effort="low",
        max_steps=8, transcript_dir=None, codex_home=str(tmp / "home"), session_turns=None,
        base_url=None, **kw)
    if kw.get("design"):
        fake_codex.reply(None, "Designed it.",
                         files={"design.md": "# Parts\nR1 Device:R 10k\n",
                                "intent.json": json.dumps(INTENT)})
    outputs = drive_kicad(agent, fake_codex)
    agent.finish(1.0, None)
    return agent, outputs


@pytest.mark.parametrize("kind", sorted(ARMS))
def test_kicad_arm(tmp_path, fake_codex, monkeypatch, kind):
    from gym_codex import memory_agents
    monkeypatch.setattr("time.sleep", lambda s: None)
    agent, outputs = _episode(kind, "codex", "task_a", tmp_path, fake_codex)
    if kind.endswith("-carry"):          # the second task sees the first one's record
        agent, outputs = _episode(kind, "codex", "task_b", tmp_path, fake_codex)
    name = f"{PINS}{kind}"
    check_pin(f"{name}_contract.md", _norm((agent.visible / "AGENTS.md").read_text(), tmp_path))
    check_pin(f"{name}_calls.json", _dump_calls(fake_codex, tmp_path))
    check_pin(f"{name}_outputs.json", json.dumps(outputs, indent=1))
    check_pin(f"{name}_workspace.txt", _manifest(tmp_path / "out", tmp_path))
    audit = agent.audit()
    audit.pop("vision_audit_source", None)
    check_pin(f"{name}_audit.json",
              _norm(json.dumps(audit, indent=1, sort_keys=True, default=str), tmp_path))
