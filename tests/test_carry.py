"""The carry rung: a task's workspace carries the finished tasks' records and a
persistent notes/ (mfm/memory/carry.py), and the store's merged index on top."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import test_pins_replay as R


def _agent(tmp_path: Path, kind: str, task: str, monkeypatch):
    from gym_codex import memory_agents
    monkeypatch.setattr("time.sleep", lambda s: None)
    task_dir = tmp_path / "out" / task
    return memory_agents.make_agent(
        kind, workspace=task_dir / "workspace", model="gpt-5.6-sol", effort="low",
        max_steps=8, transcript_dir=None, codex_home=str(tmp_path / "home"),
        session_turns=None, base_url=None,
        carry_dir=tmp_path / "out" / "carry", task_id=task), task_dir / "workspace"


def test_mfm_carry_merges_the_index_and_pushes_recall(tmp_path, fake_codex, monkeypatch):
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
    # Task B repeats task A's transitions (the same scripted replies), so the recall
    # of the MFM arms (perception + action of the last turn, mfm.memory.recall) fires
    # from the second turn on, pointing at task A's rows.
    prompts = [c["prompt"] for c in fake_codex.recorded()]
    pushed = [p for p in prompts if "[RECALL] the last turn's situation and action occurred before in an earlier task" in p]
    assert pushed, "no recall block reached a turn prompt"
    assert 'previous/A step 1: at "Placing the resistor." you did click(500,500); type("R1") -> "second batch"' in pushed[0]
    assert all(r.get("effect") for r in rows if r["kind"] == "episode" and r["first_step"] < 3)
    assert (ws_b / "previous" / "situations.md").exists()
    assert b.audit()["carry"]["previous_episodes"] == len(rows)


# -- the shared spine (mfm.memory.carry.seed_previous) -------------------------------
# Both benchmarks carry finished records the same way and name them differently: KiCad
# carries the tasks of one run (`previous/<task_id>`, rows tagged `task`), MCU carries
# earlier runs of the same world (`previous/life_<i>`, rows tagged `life`). These pin
# the part that is shared, so the two cannot drift back into two implementations.

def _record(root: Path, name: str, rows: list[dict]) -> Path:
    src = root / name
    (src / "frames").mkdir(parents=True)
    (src / "logs.txt").write_text(f"log of {name}")
    (src / "frames" / "step_0001.png").write_bytes(b"png")
    (src / "AGENTS.md").write_text("machinery, not history")
    (src / ".hidden").write_text("dotfile")
    (src / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return src


def test_seed_previous_links_the_record_and_skips_the_machinery(tmp_path):
    from mfm.memory.carry import CarriedRecord, seed_previous

    src = _record(tmp_path / "src", "task_a", [{"step": 1, "image": "frames/step_0001.png"}])
    prev = tmp_path / "ws" / "previous"
    seed = seed_previous(prev, [CarriedRecord("task_a", src, {"task": "task_a"})],
                         skip=frozenset({"AGENTS.md"}))
    assert (prev / "task_a" / "logs.txt").read_text() == "log of task_a"
    assert (prev / "task_a" / "frames" / "step_0001.png").exists()
    assert not (prev / "task_a" / "AGENTS.md").exists()      # machinery, skipped
    assert (prev / "task_a" / ".hidden").exists()            # kept unless skip_hidden
    # logs.txt, frames/step_0001.png, .hidden and index.jsonl; AGENTS.md skipped
    assert seed.linked == 4 and seed.names == ["task_a"]


def test_seed_previous_rewrites_index_paths_and_stamps_the_tag(tmp_path):
    from mfm.memory.carry import CarriedRecord, seed_previous

    a = _record(tmp_path / "src", "a", [{"step": 1, "image": "frames/step_0001.png",
                                         "path": "episodes/ep_000001"}])
    b = _record(tmp_path / "src", "b", [{"step": 2, "attachment": "frames/step_0002.png"}])
    prev = tmp_path / "ws" / "previous"
    # MCU's naming and tag; KiCad's differ only here.
    seed = seed_previous(prev, [CarriedRecord("life_1", a, {"life": 1}),
                                CarriedRecord("life_2", b, {"life": 2})],
                         skip=frozenset({"AGENTS.md"}), skip_hidden=True)
    rows = [json.loads(l) for l in (prev / "index.jsonl").read_text().splitlines()]
    assert [r["life"] for r in rows] == [1, 2]
    assert rows[0]["image"] == "previous/life_1/frames/step_0001.png"
    assert rows[0]["path"] == "previous/life_1/episodes/ep_000001"
    assert rows[1]["attachment"] == "previous/life_2/frames/step_0002.png"
    assert not (prev / "life_1" / ".hidden").exists()        # skip_hidden is MCU's rule
    assert seed.rows == rows


def test_seed_previous_tolerates_a_missing_record_and_a_broken_row(tmp_path):
    from mfm.memory.carry import CarriedRecord, seed_previous

    good = _record(tmp_path / "src", "good", [{"step": 1}])
    (good / "index.jsonl").write_text('{"step": 1}\nnot json\n\n{"step": 2}\n')
    prev = tmp_path / "ws" / "previous"
    seed = seed_previous(prev, [CarriedRecord("gone", tmp_path / "nope", {"task": "gone"}),
                                CarriedRecord("good", good, {"task": "good"})])
    assert seed.names == ["good"]                            # the absent one is skipped
    assert [r["step"] for r in seed.rows] == [1, 2]          # the unparseable line is not fatal


def test_no_previous_records_writes_no_index(tmp_path):
    from mfm.memory.carry import seed_previous

    prev = tmp_path / "ws" / "previous"
    seed = seed_previous(prev, [])
    assert seed.rows == [] and seed.linked == 0
    assert not (prev / "index.jsonl").exists()
