"""The three ablations of the MFM arm (2026-09-19), on the gen-4 chassis under
MFM_MCU_ROOT: `history_images=False` (without historical images), `flat_retrieval=True`
(without structured episode retrieval), `consolidation=False` (without long-term
consolidation). Each test drives the launched flag set (launch_g4_fasrc.sh's MFM_BASE)
with the selftest fakes and checks what the model can reach, what it is told, and what
the report says. The full arm is pinned elsewhere; here the first test also checks that
an ablation does not move the log the full arm writes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from test_pins_chassis import _norm, _pov, drive_chassis

#: launch_g4_fasrc.sh MFM_BASE, as WorldModelAgent kwargs (the launcher adds --retrieval).
LAUNCHED = dict(expect=True, frames=True, thin=True, minimal=True, atoms=True, own=True,
                own_reflexes=True, harness_reflexes=False, skills=True, event_sheet=False)
CHOP = {"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]}, "message": "[PLAN]\nchop"}


def _tool(ws: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ws / "tools" / "episodes.py"), "--root", str(ws), *args],
                          capture_output=True, text=True)


# -- 1. without historical images -----------------------------------------------------

def test_no_history_images_keeps_no_frame_and_says_so(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path / "a", "mfm", retrieval=True, history_images=False, **LAUNCHED)
    ws = agent.memory.root
    # The record: every episode, no image anywhere; the index says so on every row.
    assert (ws / "episodes").is_dir() and len(list((ws / "episodes").glob("ep_*"))) > 3
    assert not list((ws / "episodes").rglob("*.png"))
    rows = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines()]
    assert rows and all("image" in r and r["image"] is None for r in rows)
    # The log is the full arm's log byte for byte: frames never touched it.
    full, _ = drive_chassis(tmp_path / "b", "mfm", retrieval=True, **LAUNCHED)
    assert (_norm((ws / "logs.txt").read_text(), tmp_path / "a")
            == _norm((full.memory.root / "logs.txt").read_text(), tmp_path / "b"))
    assert list((full.memory.root / "episodes").rglob("image.png"))      # the full arm keeps them
    # What the model is told: the contract, the memory skill, the own reference.
    md = (ws / "AGENTS.md").read_text()
    assert "no earlier frame is kept in this run" in md and "../attach/frame.png" in md
    assert "then-now" not in md and "observation/image.png" not in md and "--sheet" not in md
    assert "tools/zoom.py" in md                                          # the current view is still croppable
    mem = (ws / "skills" / "memory" / "SKILL.md").read_text()
    assert "NO frame is kept in this run" in mem and "death_sheet" not in mem
    assert "The current view is the only frame" in mem
    assert not (ws / "skills" / "memory" / "scripts" / "death_sheet.py").exists()
    assert (ws / "skills" / "memory" / "scripts" / "where_was.py").exists()
    own_md = (ws / "references" / "own.md").read_text()
    assert "entries you would re-open" in own_md and "frames you would re-open" not in own_md
    # The turn messages: no frame path cited anywhere, the [OBSERVED] block without frames.
    text = "\n=====\n".join(agent.codex.prompts)
    assert "with the frame it started from" not in text and "frame:" not in text.lower().replace("frame.png", "")
    assert "(no frames are kept in this run)" in text
    # The query tool: listing works, the two image views say why they cannot.
    ok = _tool(ws, "--last", "3")
    assert ok.returncode == 0 and len(ok.stdout.splitlines()) == 3
    for args in (("--last", "3", "--sheet", str(tmp_path / "x.png")), ("--then-now", rows[-1]["id"])):
        cp = _tool(ws, *args)
        assert cp.returncode != 0 and "keeps no frames" in cp.stderr, args
        assert not (tmp_path / "x.png").exists()
    rep = agent.report()
    assert rep["mfm_options"]["ablations"] == ["no_history_images"]
    assert rep["mfm"]["history_images"] is False and rep["mfm"]["structured_retrieval"] is True
    assert rep["mfm"]["frames_written"] == 0 and full.report()["mfm"]["frames_written"] > 0


def test_no_history_images_carries_lives_without_frames_and_sweeps_saved_images(tmp_path: Path):
    full, _ = drive_chassis(tmp_path / "seed", "mfm", **LAUNCHED)
    seed = full.memory.root
    assert list((seed / "episodes").rglob("image.png"))
    # Turn 1 saves an "image" under mine/ (the sweep is by suffix); the rest chop.
    script = [{**CHOP, "files": {"mine/keep.png": {"a": 1}, "mine/notes.md": {"n": 1}}}] + [CHOP] * 20
    agent, _ = drive_chassis(tmp_path / "life", "mfm", history_images=False,
                             previous_lives=[str(seed)], script=script, **LAUNCHED)
    ws = agent.memory.root
    assert (ws / "previous" / "life_1" / "logs.txt").exists()
    assert not list((ws / "previous").rglob("*.png")) and not list((ws / "previous").rglob("*.jpg"))
    prev_rows = [json.loads(l) for l in (ws / "previous" / "index.jsonl").read_text().splitlines()]
    assert prev_rows and all(r["image"] is None for r in prev_rows)
    assert all(r["path"].startswith("previous/life_1/") for r in prev_rows)
    assert not (ws / "mine" / "keep.png").exists()                       # swept before the next turn
    assert (ws / "mine" / "notes.md").exists()                            # notes are not images
    assert agent.report()["mfm_options"]["history_image_sweeps"] >= 1
    md = (ws / "AGENTS.md").read_text()
    assert "no frames\nare kept in this run" in md.replace("(no frames\nare", "(no frames\nare") or "no frames" in md
    assert (_tool(ws, "--previous", "--last", "2").returncode == 0)
    cp = _tool(ws, "--previous", "--last", "2", "--sheet", str(tmp_path / "p.png"))
    assert cp.returncode != 0 and "keeps no frames" in cp.stderr


# -- 2. without structured episode retrieval -----------------------------------------

def test_flat_retrieval_keeps_the_record_and_removes_the_addressing_layer(tmp_path: Path):
    agent, _ = drive_chassis(tmp_path, "mfm", flat_retrieval=True, **LAUNCHED)
    ws = agent.memory.root
    # The same record: episodes with their frames, the chronological index; no tool.
    assert list((ws / "episodes").rglob("image.png"))
    rows = [json.loads(l) for l in (ws / "index.jsonl").read_text().splitlines()]
    assert rows and all(r["image"] for r in rows if r["kind"] == "episode")
    assert rows == sorted(rows, key=lambda r: r["first_step"])
    assert not (ws / "tools" / "episodes.py").exists() and (ws / "tools" / "zoom.py").exists()
    # Nothing index-based reaches the prompt; the model is told to grep.
    text = "\n=====\n".join(agent.codex.prompts)
    assert "[RECALL]" not in text and "tools/episodes.py" not in text
    assert "`rg` them; `view_image` opens a frame" in text
    md = (ws / "AGENTS.md").read_text()
    assert "tools/episodes.py" not in md and "there is no query tool" in md
    assert "view_image episodes/<id>/observation/image.png" in md
    for f in ("skills/memory/SKILL.md", "references/own.md"):
        assert "tools/episodes.py" not in (ws / f).read_text(), f
    mem = (ws / "skills" / "memory" / "SKILL.md").read_text()
    assert "There is NO query tool in this run" in mem and "index.jsonl" in mem
    assert not (ws / "skills" / "memory" / "scripts" / "death_sheet.py").exists()
    rep = agent.report()
    assert rep["mfm_options"]["ablations"] == ["flat_retrieval"]
    assert rep["mfm"]["structured_retrieval"] is False and rep["mfm"]["history_images"] is True
    assert rep["mfm"]["retrieval"] is False and rep["mfm"]["recalls"] == 0
    # The two index-based mechanisms cannot be combined with it.
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "x", "mfm", flat_retrieval=True, retrieval=True, **LAUNCHED)
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "y", "mfm", flat_retrieval=True, refusal=True, **LAUNCHED)


def test_flat_retrieval_with_carried_lives_points_at_the_merged_index(tmp_path: Path):
    full, _ = drive_chassis(tmp_path / "seed", "mfm", **LAUNCHED)
    agent, _ = drive_chassis(tmp_path / "life", "mfm", flat_retrieval=True,
                             previous_lives=[str(full.memory.root)], **LAUNCHED)
    ws = agent.memory.root
    assert (ws / "previous" / "index.jsonl").exists() and not (ws / "tools" / "episodes.py").exists()
    md = (ws / "AGENTS.md").read_text()
    assert "previous/index.jsonl" in md and "--previous" not in md
    assert "previous/index.jsonl` merges their indexes" in (ws / "skills" / "memory" / "SKILL.md").read_text()


# -- 3. without long-term consolidation ----------------------------------------------

class _RawFakeCodex:
    """The selftest fake with raw file writes (a verbatim copy of an example script
    cannot be expressed as JSON)."""

    def __init__(self, inner, raw: dict[int, dict[str, bytes]]):
        self._inner, self._raw = inner, raw

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run(self, prompt, images=(), **kw):
        out = self._inner.run(prompt, images, **kw)
        for rel, data in self._raw.get(self._inner.calls, {}).items():
            p = self._inner.workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return out


def _drive_no_consolidation(root: Path, raw: dict[int, dict[str, bytes]], script, seed_mine: dict[str, bytes] | None = None):
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import FakeCodex, fake_info

    cfg = [{"event": "craft_item", "identity": "iron_pickaxe", "objects": ["iron_pickaxe"],
            "reward": 1.0, "max_reward_times": 1}]
    ws = root / "ws"
    for rel, data in (seed_mine or {}).items():                  # the life's initial memory
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_bytes(data)
    agent = WorldModelAgent(workspace=ws, task_text="an iron pickaxe", ledger=MilestoneLedger(cfg, "t"), step_cap=50, memory_mode="mfm",
                            platform_prompt="HOST REFERENCE", consolidation=False, **LAUNCHED)
    agent.codex = _RawFakeCodex(FakeCodex(agent.memory.root, script), raw)
    info = fake_info(inventory={"oak_log": 1})
    info["pov"] = _pov(0)
    agent.start(info)
    snapshots = []
    for step in range(1, 80):
        agent.next_action(info)
        info = fake_info(inventory={"oak_log": 1})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["pov"] = _pov(step)
        agent.observe(info, step)
        snapshots.append((agent.codex.calls, sorted(p.relative_to(agent.memory.root).as_posix()
                                                    for p in (agent.memory.root / "mine").rglob("*") if p.is_file())))
    return agent, snapshots


def test_no_consolidation_keeps_working_md_and_unchanged_examples_only(tmp_path: Path):
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path / "ref")                           # the examples' bytes
    lava = (tmp_path / "ref" / "skills" / "reflexes" / "scripts" / "lava_ahead.py").read_bytes()
    hit = (tmp_path / "ref" / "skills" / "reflexes" / "scripts" / "hit.py").read_bytes()
    torch = (tmp_path / "ref" / "skills" / "procedures" / "scripts" / "torch_wall.py").read_bytes()
    foo = b'"""foo: a new procedure."""\nimport json\nprint(json.dumps({"actions": [{"action": {"jump": 1}, "repeat": 2}]}))\n'
    raw = {1: {"mine/notes.md": b"lava at (10, 12, -20)\n",
               "mine/digest.md": b"# digest\n",
               "mine/working.md": b"plan: chop, then dig\n",
               "mine/procedures/foo.py": foo,
               "mine/procedures/tw.py": torch,                    # an example, renamed, unchanged
               "mine/reflexes/lava_ahead.py": lava,               # an example, unchanged
               "mine/reflexes/hit.py": hit + b"\n# tuned\n",       # an example, edited
               "mine/GUIDE.md": b"edited guide\n"}}               # initial memory, edited
    script = [{"actions": {"actions": [{"procedure": "foo"}, {"procedure": "tw"},
                                       {"action": {"attack": 1}, "repeat": 6}]},
               "message": "[PLAN]\nwrite files, call foo and tw"}] + [CHOP] * 20
    agent, snaps = _drive_no_consolidation(tmp_path, raw, script, seed_mine={"mine/GUIDE.md": b"seed guide\n"})
    ws = agent.memory.root
    # The turn that wrote them: foo is refused as not kept, the unchanged example runs.
    log = (ws / "logs.txt").read_text()
    assert "foo (mine/procedures/foo.py) FAILED, nothing ran: not kept in this run" in log
    assert "tw (mine/procedures/tw.py) FAILED, nothing ran: not kept" not in log
    # From the next turn on: working.md, the unchanged copies and the restored seed file.
    after = {rel for calls, files in snaps if calls >= 2 for rel in files}
    assert after == {"mine/GUIDE.md", "mine/working.md", "mine/procedures/tw.py", "mine/reflexes/lava_ahead.py"}, after
    assert (ws / "mine" / "GUIDE.md").read_bytes() == b"seed guide\n"     # the edit was undone
    assert (ws / "mine" / "working.md").read_bytes() == b"plan: chop, then dig\n"
    assert not (ws / "mine" / "reflexes" / "hit.py").exists() and not (ws / "mine" / "notes.md").exists()
    text = "\n=====\n".join(agent.codex.prompts)
    assert "[WORKING] mine/working.md" in text and "plan: chop, then dig" in text
    assert "`tw(" in text and "`foo(" not in text.split("=====")[-1]
    # What the model is told, everywhere it would look.
    md = (ws / "AGENTS.md").read_text()
    assert "the ONE file of yours that is kept" in md
    assert "UNCHANGED (in this run an edited copy" in md
    own_md = (ws / "references" / "own.md").read_text()
    assert "not kept in this run" in own_md and "byte-identical copy" in own_md
    assert "It is\nthe ONE file of yours that persists" in own_md
    for name in ("procedures", "reflexes", "harness"):
        assert "## This run" in (ws / "skills" / name / "SKILL.md").read_text(), name
    mem = (ws / "skills" / "memory" / "SKILL.md").read_text()
    assert "NOT kept in this run, except `mine/working.md`" in mem and "one line in your BRIEFING" in mem
    rep = agent.report()
    assert rep["mfm_options"]["ablations"] == ["no_consolidation"]
    cons = rep["mfm_options"]["consolidation"]
    assert cons["snapshot_files"] == 1 and cons["removed"] >= 4 and cons["restored"] >= 1
    assert cons["turns"] == agent.codex.calls
    # The record itself is untouched by the freeze.
    assert (ws / "tools" / "episodes.py").exists() and list((ws / "episodes").rglob("image.png"))


def test_no_consolidation_needs_own_and_the_full_flag_set_is_unchanged(tmp_path: Path):
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "x", "mfm", consolidation=False)
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "y", "logbook", history_images=False)
    agent, _ = drive_chassis(tmp_path / "z", "mfm", retrieval=True, **LAUNCHED)
    rep = agent.report()
    assert "ablations" not in rep["mfm_options"] and "consolidation" not in rep["mfm_options"]
    assert "history_images" not in rep["mfm"]
    assert (agent.memory.root / "tools" / "episodes.py").exists()


# -- the rollout measures --------------------------------------------------------------

def test_rollout_scan_counts_past_frame_views_and_record_searches(tmp_path: Path):
    from mcu_worldmodel.codex_backend import scan_rollout

    ws = "/x/output/arm/episode_001/memory"
    lines = [
        {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": f"{ws}/episodes/ep_000010/observation/image.png"})},
        {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": f"{ws}/previous/life_1/episodes/ep_000003/observation/image.png"})},
        {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": "/x/output/arm/episode_001/hires/0000123.jpg"})},
        {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": f"{ws}/../attach/frame.png"})},   # the present
        {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": "/tmp/zoom.png"})},                 # a crop
        {"type": "custom_tool_call", "name": "exec", "input": "tools.exec_command({cmd: \"rg -n stuck index.jsonl | head\"}); tools.exec_command({cmd: \"grep -c YOU logs.txt\"}); tools.exec_command({cmd: \"ls mine\"})"},
        {"type": "message", "role": "user", "content": "the contract mentions rg index.jsonl and view_image episodes/ep_000001/observation/image.png"},
    ]
    p = tmp_path / "rollout-x.jsonl"
    p.write_text("".join(json.dumps({"type": "response_item", "payload": l}) + "\n" for l in lines))
    out = scan_rollout(p)
    assert out["view_image_calls"] == 5
    assert out["history_image_views"] == 3           # episode, previous life, hires; not attach/ or /tmp
    assert out["record_search_calls"] == 2           # rg index.jsonl, grep logs.txt; not ls mine


def test_no_history_images_closes_the_hires_channel_and_the_event_sheet(tmp_path: Path):
    """The frame record beside the workspace is readable through the sandbox (the v6
    diamond life opened ../hires/ five times): written unreadable under the ablation.
    The event sheet attaches this turn's past frames: forced off."""
    import base64
    import io
    import stat

    adapter = pytest.importorskip("worldmodel_purple_agent")
    from PIL import Image

    ex = adapter.WorldModelExecutor(workspace_root=tmp_path / "out", model="m", codex_home=None,
                                    memory_mode="mfm", history_images=False)
    ex._hires_dir = tmp_path / "hires"
    ex._hires_dir.mkdir()
    buf = io.BytesIO()
    Image.new("RGB", (8, 4), (200, 30, 30)).save(buf, format="JPEG")
    ex._step = 7
    ex._keep_hires(base64.b64encode(buf.getvalue()).decode())
    files = list(ex._hires_dir.iterdir())
    assert len(files) == 1 and files[0].name == "0000007.jpg"
    assert stat.S_IMODE(files[0].stat().st_mode) == 0
    full = adapter.WorldModelExecutor(workspace_root=tmp_path / "out2", model="m", codex_home=None,
                                      memory_mode="mfm")
    full._hires_dir = tmp_path / "hires2"
    full._hires_dir.mkdir()
    full._step = 7
    full._keep_hires(base64.b64encode(buf.getvalue()).decode())
    assert stat.S_IMODE((full._hires_dir / "0000007.jpg").stat().st_mode) & stat.S_IRUSR
    agent, _ = drive_chassis(tmp_path / "a", "mfm", history_images=False, **{**LAUNCHED, "event_sheet": True})
    assert agent.event_sheet is False and agent.report()["mfm_options"]["event_sheet"] is False


# -- 4. without agent-written procedures (2026-09-23) ---------------------------------

def _drive_ablated(root: Path, raw: dict[int, dict[str, bytes]], script, **flags):
    """Like _drive_no_consolidation, for any ablation flag set on top of LAUNCHED."""
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import FakeCodex, fake_info

    cfg = [{"event": "craft_item", "identity": "iron_pickaxe", "objects": ["iron_pickaxe"],
            "reward": 1.0, "max_reward_times": 1}]
    agent = WorldModelAgent(workspace=root / "ws", task_text="an iron pickaxe", ledger=MilestoneLedger(cfg, "t"),
                            step_cap=50, memory_mode="mfm", platform_prompt="HOST REFERENCE", **{**LAUNCHED, **flags})
    agent.codex = _RawFakeCodex(FakeCodex(agent.memory.root, script), raw)
    info = fake_info(inventory={"oak_log": 1})
    info["pov"] = _pov(0)
    agent.start(info)
    for step in range(1, 80):
        agent.next_action(info)
        info = fake_info(inventory={"oak_log": 1})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["pov"] = _pov(step)
        agent.observe(info, step)
    return agent


def test_no_own_procedures_keeps_mine_but_never_runs_a_script(tmp_path: Path):
    from mcu_worldmodel import skills

    skills.write_skills(tmp_path / "ref")                           # the full arm's examples
    torch = (tmp_path / "ref" / "skills" / "procedures" / "scripts" / "torch_wall.py").read_bytes()
    lava = (tmp_path / "ref" / "skills" / "reflexes" / "scripts" / "lava_ahead.py").read_bytes()
    foo = b'"""foo: a new procedure."""\nimport json\nprint(json.dumps({"actions": [{"action": {"jump": 1}, "repeat": 2}]}))\n'
    raw = {1: {"mine/notes.md": b"recipe: look, then mine_ahead 70\n",
               "mine/digest.md": b"# digest\n",
               "mine/working.md": b"plan: chop, then dig\n",
               "mine/procedures/foo.py": foo,                     # the model's own script
               "mine/procedures/tw.py": torch,                    # an unchanged harness example
               "mine/reflexes/lava_ahead.py": lava}}              # a reflex: still allowed
    script = [{"actions": {"actions": [{"procedure": "foo"}, {"procedure": "tw"},
                                       {"action": {"attack": 1}, "repeat": 6}]},
               "message": "[PLAN]\nwrite files, call foo and tw"}] + [CHOP] * 20
    agent = _drive_ablated(tmp_path, raw, script, own_procedures=False)
    ws = agent.memory.root
    # Neither script ran -- not the model's own, not the unchanged example -- with the reason.
    log = (ws / "logs.txt").read_text()
    assert "foo (mine/procedures/foo.py) FAILED, nothing ran: not run in this run" in log
    assert "tw (mine/procedures/tw.py) FAILED, nothing ran: not run in this run" in log
    assert "agent-written procedures are ablated" in log
    # mine/ is kept whole: the notes, the digest, the scripts and the reflex all survive.
    kept = {p.relative_to(ws).as_posix() for p in (ws / "mine").rglob("*") if p.is_file()}
    assert {"mine/notes.md", "mine/digest.md", "mine/working.md", "mine/procedures/foo.py",
            "mine/procedures/tw.py", "mine/reflexes/lava_ahead.py"} <= kept, kept
    # The turn prompt lists the scripts as NOT callable, and the working note still shows.
    text = "\n=====\n".join(agent.codex.prompts)
    assert "`foo` -- NOT callable: not run in this run" in text
    assert "`tw` -- NOT callable: not run in this run" in text
    assert "[WORKING] mine/working.md" in text and "plan: chop, then dig" in text
    # What the model is told, everywhere it would look.
    md = (ws / "AGENTS.md").read_text()
    assert "a composition cannot be kept as a procedure of your own" in md
    assert "no script under `mine/procedures/` runs in this run" in md
    assert "reflexes only: in this run NO script under `mine/procedures/` runs" in md
    own_md = (ws / "references" / "own.md").read_text()
    assert "procedures are not run in this run" in own_md and "NOT callable" in own_md
    assert "[WORKING]" in own_md                                       # the working note contract is unchanged
    for name in ("procedures", "harness"):
        assert "## This run" in (ws / "skills" / name / "SKILL.md").read_text(), name
    assert "## This run" not in (ws / "skills" / "reflexes" / "SKILL.md").read_text()
    mem = (ws / "skills" / "memory" / "SKILL.md").read_text()
    assert "`mine/procedures/` is NOT run in" in mem and "copy the reflexes worth keeping" in mem
    assert not (ws / "skills" / "procedures" / "scripts").exists()     # no runnable example shipped
    assert (ws / "skills" / "reflexes" / "scripts" / "lava_ahead.py").exists()
    # The report names the ablation and shows zero calls.
    rep = agent.report()
    assert rep["mfm_options"]["ablations"] == ["no_own_procedures"]
    assert rep["own"]["procedures_run"] is False and rep["own"]["calls"] == {}
    assert rep["own"]["procedures"] == 2
    # The record itself is untouched.
    assert (ws / "tools" / "episodes.py").exists() and list((ws / "episodes").rglob("image.png"))


def test_no_own_procedures_needs_own_and_does_not_touch_the_full_arm(tmp_path: Path):
    with pytest.raises(ValueError):
        drive_chassis(tmp_path / "x", "mfm", own_procedures=False)
    agent, _ = drive_chassis(tmp_path / "z", "mfm", retrieval=True, **LAUNCHED)
    rep = agent.report()
    assert "ablations" not in rep["mfm_options"] and "procedures_run" not in rep["own"]
    from mcu_worldmodel import own, skills
    assert own.own_note() == own.MFM_OWN_NOTE and skills.skills_note() == skills.SKILLS_NOTE
    assert own.atoms_line() == own.ATOMS_LINE
