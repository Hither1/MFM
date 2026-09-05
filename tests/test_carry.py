"""The carry rung: a task's workspace carries the finished tasks' records and a
persistent notes/ (mfm/memory/carry.py), and the store's merged index on top."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import test_pins_replay as R
from conftest import pin_path


def _agent(tmp_path: Path, kind: str, task: str, monkeypatch):
    from gym_codex import memory_agents
    monkeypatch.setattr(memory_agents.time, "sleep", lambda s: None)
    task_dir = tmp_path / "out" / task
    return memory_agents.make_agent(
        kind, workspace=task_dir / "workspace", model="gpt-5.6-sol", effort="low",
        max_steps=8, transcript_dir=None, codex_home=str(tmp_path / "home"),
        session_turns=None, base_url=None,
        carry_dir=tmp_path / "out" / "carry", task_id=task), task_dir / "workspace"


def test_prolong_carry_links_records_and_persists_notes(tmp_path, fake_codex, monkeypatch):
    a, ws_a = _agent(tmp_path, "prolong-carry", "A", monkeypatch)
    R.drive_kicad(a, fake_codex)
    assert "first task of the sequence" in (ws_a / "AGENTS.md").read_text()
    assert not (ws_a / "previous").exists() or not any((ws_a / "previous").iterdir())
    (ws_a / "notes" / "recipes.md").write_text("press a for the symbol chooser\n")
    a.finish(1.0, None)
    manifest = json.loads((tmp_path / "out" / "carry" / "manifest.json").read_text())
    assert [m["task_id"] for m in manifest] == ["A"] and manifest[0]["reward"] == 1.0

    b, ws_b = _agent(tmp_path, "prolong-carry", "B", monkeypatch)
    R.drive_kicad(b, fake_codex)
    b.finish(0.0, None)
    # The record, not a copy of its machinery, and the log is byte-identical.
    assert (ws_b / "previous" / "A" / "logs.txt").read_text() == (ws_a / "logs.txt").read_text()
    assert sorted(p.name for p in (ws_b / "previous" / "A" / "frames").iterdir()) == \
        sorted(p.name for p in (ws_a / "frames").iterdir())
    for own in ("AGENTS.md", "actions.json", "tools", "previous", "notes"):
        assert not (ws_b / "previous" / "A" / own).exists(), own
    assert (ws_b / "notes" / "recipes.md").read_text() == "press a for the symbol chooser\n"
    assert "1 task(s) are recorded under `previous/`" in (ws_b / "AGENTS.md").read_text()
    assert not (ws_b / "previous" / "index.jsonl").exists()      # no store on this rung
    assert b.audit()["carry"] == {"previous_tasks": 1, "files_linked": b.carry.seeded,
                                  "previous_episodes": 0, "notes_files": 1}
    # This task's own log and prompts are the baseline's plus the carry paragraph only.
    assert R._norm((ws_b / "logs.txt").read_text(), tmp_path) == pin_path("kicad_logs.txt").read_text()
    assert [m["task_id"] for m in json.loads((tmp_path / "out" / "carry" / "manifest.json").read_text())] == ["A", "B"]


def test_mfm_carry_merges_the_index_and_pushes_seen_before(tmp_path, fake_codex, monkeypatch):
    a, ws_a = _agent(tmp_path, "mfm-carry", "A", monkeypatch)
    R.drive_kicad(a, fake_codex)
    a.finish(1.0, None)
    b, ws_b = _agent(tmp_path, "mfm-carry", "B", monkeypatch)
    R.drive_kicad(b, fake_codex)
    b.finish(0.0, None)

    merged = ws_b / "previous" / "index.jsonl"
    rows = [json.loads(l) for l in merged.read_text().splitlines() if l.strip()]
    assert rows and all(r["task"] == "A" and r["path"].startswith("previous/A/episodes/") for r in rows)
    assert all((ws_b / r["image"]).exists() for r in rows if r.get("image"))
    assert "--previous" in (ws_b / "AGENTS.md").read_text()

    tool = ws_b / "tools" / "episodes.py"
    out = subprocess.run([sys.executable, str(tool), "--previous", "--last", "3"],
                         capture_output=True, text=True, cwd=ws_b)
    assert out.returncode == 0 and "previous/A/episodes/" in out.stdout, out.stderr
    # Task B's screens are task A's screens (the same scripted frames), so the exact
    # screen is found across tasks, by the tool and by the pushed line.
    frame = sorted((ws_b / "frames").iterdir())[1]
    out = subprocess.run([sys.executable, str(tool), "--previous", "--same-screen", str(frame)],
                         capture_output=True, text=True, cwd=ws_b)
    assert out.returncode == 0 and "previous/A/" in out.stdout, out.stderr
    prompts = [c["prompt"] for c in fake_codex.recorded()]
    pushed = [p for p in prompts if "[SEEN BEFORE] this exact screen appeared in earlier tasks" in p]
    assert pushed, "no seen-before line reached a turn prompt"
    assert "previous/A step" in pushed[0]
    assert b.audit()["carry"]["previous_episodes"] == len(rows)
