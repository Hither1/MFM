"""The byte-budgeted persistent session: `run-arm.sh --session-turns 0 --session-bytes B`
(the arms' default from 2026-09-09; `--session-turns 1` is the policy the earlier waves ran).

One codex thread carries across turns. Codex re-sends every earlier frame on each resumed
call, and past ~5.5 MB on the wire every turn stalls (run-arm.sh header), so the turn
whose frame would push the payload past the budget cold-starts instead -- VISTA's
`thread_bytes_budget` with the filesystem as the checkpoint. Both backends; the audit
keys appear only when the budget is on, so the baseline arm's pinned key set does not move.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import ROOT

FRAME = 750_000                      # bytes on disk; 1_000_000 base64 on the wire
BUDGET = 3_500_000                   # three frames fit, the fourth would not


def _frames(tmp_path: Path, n: int) -> list[Path]:
    out = []
    for i in range(n):
        p = tmp_path / f"frame_{i}.png"
        p.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes([i % 251]) * (FRAME - 8))
        out.append(p)
    return out


def _backend(kind: str, tmp_path: Path, **kw):
    home = tmp_path / f"home_{kind}"
    ws = tmp_path / f"ws_{kind}"
    ws.mkdir(parents=True)
    if kind == "chassis":
        from mcu_worldmodel.codex_backend import CodexTurn
    else:
        from prolong_mc.codex_backend import CodexTurn
    return CodexTurn(ws, model="gpt-5.6-sol", codex_home=home, **kw)


@pytest.mark.parametrize("kind", ["chassis", "shared"])
def test_the_frame_that_would_cross_the_budget_cold_starts(tmp_path, fake_codex, kind):
    for _ in range(5):
        fake_codex.reply({"actions": []}, "[PLAN]\nok")
    codex = _backend(kind, tmp_path, session_max_turns=0, session_max_bytes=BUDGET)
    for frame in _frames(tmp_path, 5):
        result = codex.run("act", images=[frame])
        assert result["ok"], result
    # 1.0 MB, 2.0, 3.0 on one thread; 4.0 would cross 3.5, so turn 4 is a cold start and
    # turn 5 resumes the new thread at 2.0.
    assert [c["resume"] for c in fake_codex.recorded()] == [False, True, True, False, True]
    assert codex.bytes_resets == 1 and codex.age_resets == 0
    assert codex.session_attachment_bytes == 2_000_000
    assert codex.peak_attachment_bytes == 3_000_000
    audit = codex.vision_audit()
    assert audit["bytes_resets"] == 1 and audit["session_max_bytes"] == BUDGET
    assert audit["age_resets"] == 0


@pytest.mark.parametrize("kind", ["chassis", "shared"])
def test_no_budget_means_no_new_audit_keys(tmp_path, fake_codex, kind):
    """The pinned key set (tests/pins/mcu_audit_keys.json) is the baseline's; the budget
    reports itself only where it is in force."""
    fake_codex.reply({"actions": []}, "ok")
    codex = _backend(kind, tmp_path, session_max_turns=1)
    assert codex.session_max_bytes == 0
    codex.run("act", images=_frames(tmp_path, 1))
    audit = codex.vision_audit()
    assert "bytes_resets" not in audit and "session_max_bytes" not in audit


def test_the_environment_sets_the_budget_when_the_caller_does_not(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_SESSION_MAX_BYTES", "123")
    for kind in ("chassis", "shared"):
        assert _backend(kind, tmp_path).session_max_bytes == 123
        assert _backend(kind, tmp_path / kind, session_max_bytes=0).session_max_bytes == 0


def test_the_launcher_defaults_to_one_budgeted_thread():
    """run-arm.sh's plan line, before it touches the machine."""
    script = ROOT / "MCU" / "scripts" / "run-arm.sh"
    plan = subprocess.run(
        ["bash", str(script), "--arm", "t", "--agent", "logbook",
         "--green-port", "1", "--purple-port", "2", "--dry-run"],
        capture_output=True, text=True, check=True).stdout
    assert "one thread, cold-started before 4000000 bytes of frames" in plan, plan
    text = script.read_text()
    assert text.count('--session-turns "$SESSION_TURNS" --session-bytes "$SESSION_BYTES"') >= 9
    old = subprocess.run(
        ["bash", str(script), "--arm", "t", "--agent", "logbook", "--session-turns", "1",
         "--green-port", "1", "--purple-port", "2", "--dry-run"],
        capture_output=True, text=True, check=True).stdout
    assert "dropped after 1 turn(s)" in old, old
