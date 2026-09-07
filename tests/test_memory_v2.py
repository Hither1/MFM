"""Memory v2 (2026-09-08): frames into decisions, working memory, the minimal contract,
the distiller workspace. Evidence behind each: tasks/mfm-three-layer.spatial-grid/analysis/."""
import json
import os
import sys
from pathlib import Path

import pytest

MCU = Path(os.environ.get("MFM_MCU_ROOT", Path(__file__).resolve().parents[1] / "MCU"))
sys.path.insert(0, str(MCU))


def test_bearing_names_direction_and_distance():
    from mfm.memory import retrieve as R
    assert R.bearing((0.0, 0.0), {"x": 3.0, "z": -4.0}) == "5 blocks NE"
    assert R.bearing((0.0, 0.0), {"x": 0.0, "z": 10.0}) == "10 blocks S"
    assert R.bearing((0.0, 0.0), {"x": -7.0, "z": 0.2}) == "7 blocks W"
    assert R.bearing((0.0, 0.0), {"x": 0.3, "z": 0.3}) == "here"
    assert R.bearing(None, {"x": 1.0, "z": 1.0}) == ""
    assert R.bearing((0.0, 0.0), {"x": None}) == ""


def _png(path: Path, color=(120, 80, 40)):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), color).save(path)


def test_then_now_tiles_the_remembered_frame_beside_the_current_view(tmp_path: Path):
    from mfm.memory.tools import episodes as T
    from PIL import Image
    root = tmp_path / "memory"
    _png(root / "episodes/ep_000007/observation/image.png")
    _png(root.parent / "attach" / "frame.png", (10, 200, 10))
    (root / "index.jsonl").write_text(json.dumps({
        "id": "ep_000007", "kind": "episode", "first_step": 120, "last_step": 140,
        "x": -3010.2, "y": 71.0, "z": -5572.7, "image": "episodes/ep_000007/observation/image.png",
        "path": "episodes/ep_000007", "tags": [], "summary": "walk"}) + "\n")
    out, label = T.then_now(root, "ep_000007", None, root / "then_now.png")
    assert out.exists() and label == "THEN ep_000007 step 120 at (-3010,-5573)"
    im = Image.open(out)
    assert im.height == 378 and im.width > 2 * 360          # two 360-high panes and a gap
    # a frame path works too, and a missing target is said plainly
    out2, label2 = T.then_now(root, "episodes/ep_000007/observation/image.png", None, root / "tn2.png")
    assert out2.exists() and label2.startswith("THEN episodes/")
    with pytest.raises(SystemExit):
        T.then_now(root, "ep_999999", None, root / "tn3.png")
    # the CLI: --then-now with --q prints the question back
    rc = T.main(["--root", str(root), "--then-now", "ep_000007", "--q", "same shaft?", "--out", str(root / "tn4.png")])
    assert rc == 0 and (root / "tn4.png").exists()


def test_working_block_reads_the_models_note_and_caps_it(tmp_path: Path):
    from mcu_worldmodel.agent import WorldModelAgent

    class Mem:
        root = tmp_path

    class Fake:
        own = True
        memory = Mem()
        WORKING_CAP = WorldModelAgent.WORKING_CAP
    fake = Fake()
    assert WorldModelAgent._working_block(fake) == ""             # no file: no block
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "working.md").write_text("plan: dig to y12 at the recorded column\nexpect: iron_ore in view\n")
    block = WorldModelAgent._working_block(fake)
    assert block.startswith("[WORKING] mine/working.md") and "dig to y12" in block
    (tmp_path / "mine" / "working.md").write_text("x" * 5000)
    block = WorldModelAgent._working_block(fake)
    assert "3500 more chars" in block and len(block) < 1700
    fake.own = False
    assert WorldModelAgent._working_block(fake) == ""             # not an own arm: nothing


def test_minimal_contract_is_short_and_points_at_the_references():
    from mcu_worldmodel import prompts
    full = prompts.act_prompt(task_text="Kill the dragon", progress_block="0/24", graph_summary="",
                              plan_summary="", discipline_summary="", entry_cap=6, step_cap=400,
                              memory_mode="mfm", retrieval=True, previous=True, expect=True,
                              frames=True, own=True, atoms=True, own_reflexes=True,
                              harness_reflexes=False)
    thin, refs = prompts.thin_split(full)
    tail = thin[thin.index("**References.**"):]
    m = prompts.minimal_contract(task_text="Kill the dragon", progress_block="0/24", entry_cap=6,
                                 step_cap=400, atoms=True, frames=True, harness_reflexes=False,
                                 references_tail=tail)
    assert len(m.split()) < 0.35 * len(full.split())
    for must in ("**Task**: Kill the dragon", "OBSERVED vs EXPECTED", "EXPECT:", "`view_image <png>`",
                 "--then-now", "mine/working.md", "**Safety.**", "does not guard you",
                 "**Procedures**", "references/procedures.md", "**References.**",
                 "deleted before your turn starts", '{"actions": [...]}'):
        assert must in m, must
    assert "**Crafting is ONE call.**" not in m and "**Survival**" not in m
    on = prompts.minimal_contract(task_text="t", progress_block="p", entry_cap=6, step_cap=400,
                                  harness_reflexes=True)
    assert "reflexes of its own" in on and "tools/zoom.py" not in on


def test_distill_workspace_links_the_lives_and_writes_the_tool_and_skills(tmp_path: Path):
    from mcu_worldmodel import distill
    seed = tmp_path / "seed" / "memory"
    seed.mkdir(parents=True)
    (seed / "logs.txt").write_text("Action 0 | Step 0 | INITIAL STATE\n\nTask: t\n[STATE] pos=(1.0, 70.0, 2.0) pitch=0 yaw=0\n")
    _png(seed / "episodes/ep_000000/observation/image.png")
    (seed / "index.jsonl").write_text(json.dumps({"id": "ep_000000", "kind": "initial", "first_step": 0,
                                                  "last_step": 0, "x": 1.0, "y": 70.0, "z": 2.0,
                                                  "image": "episodes/ep_000000/observation/image.png",
                                                  "path": "episodes/ep_000000", "tags": ["initial"],
                                                  "summary": "initial state"}) + "\n")
    (seed / "mine").mkdir(); (seed / "mine" / "notes.md").write_text("a note\n")
    mem = distill.build_workspace(tmp_path / "out", [seed])
    assert (mem / "previous" / "life_1" / "logs.txt").exists()
    assert (mem / "previous" / "life_1" / "mine" / "notes.md").exists()
    assert (mem / "tools" / "episodes.py").exists() and os.access(mem / "tools" / "episodes.py", os.X_OK)
    assert (mem / "skills" / "reflexes" / "scripts" / "known_hazards.py").exists()
    assert (mem / "mine").is_dir() and not list((mem / "mine").iterdir())
    assert not (mem / "mine" / "reflexes").exists()            # examples only, no starters
    prompt = distill.DISTILL_PROMPT.format(minutes=40)
    for must in ("mine/GUIDE.md", "UNDER THEIR ORIGINAL NAMES", "mine/frames.md", "known_hazards.py",
                 "Do not invent a coordinate", "about 40 minutes"):
        assert must in prompt, must
    args = distill._args("codex", "gpt-5.6-sol", "xhigh", tmp_path / "out")
    assert args[:2] == ["codex", "exec"] and "-m" in args and args[-1] == "-" and "-i" not in args
    assert 'sandbox_mode="workspace-write"' in args
    rep = distill.audit(mem)
    assert rep["guide_lines"] == 0 and rep["procedures"] == [] and rep["files"] == []
    with pytest.raises(SystemExit):
        distill.build_workspace(tmp_path / "out", [seed])       # never over an existing one


def test_expect_block_cites_the_entrys_frame(tmp_path: Path):
    from test_pins_chassis import drive_chassis
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5}]},
         "message": "briefing one\nEXPECT: moved about 1 block east\n[PLAN]\nwalk"},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
          "message": f"OBSERVED vs EXPECTED: matched\n[PLAN]\nchop {i}\nEXPECT: a log"} for i in range(6)]
    agent, _ = drive_chassis(tmp_path, "mfm", steps=40, script=script, expect=True)
    second = next(p for p in agent.codex.prompts[1:] if "[EXPECTED]" in p)
    observed = second.split("[OBSERVED]")[1].split("Begin your briefing")[0]
    assert "frame: episodes/ep_" in observed, observed


def test_raw_nudges_leave_the_streak_statistic_and_a_real_walk_counts_as_change():
    from mfm.memory import retrieve as R
    def row(i, kind, a, b, summary, tags=()):
        return {"id": f"ep_{i:06d}", "kind": "episode", "action_kind": kind, "first_step": a,
                "last_step": b, "x": 0.0, "z": 0.0, "tags": list(tags), "summary": summary}
    nudges = [row(i, "forward", 10 * i, 10 * i + 1, '[ACTION] {"forward":1} x1 -> 1 ticks: moved 0.1')
              for i in range(1, 8)]
    assert all(R.raw_nudge(r) for r in nudges)
    assert R.streaks(nudges, min_len=3) == []                      # not a loop, a habit
    walks = [row(10 + i, "forward", 100 + 30 * i, 120 + 30 * i,
                 '[ACTION] {"forward":1} x20 -> 20 ticks: moved 0.0') for i in range(4)]
    s = R.streaks(walks, min_len=3)
    assert s and s[0]["kind"] == "forward" and s[0]["n"] == 4      # four held walks that went nowhere
    good = row(20, "forward+sprint", 300, 330, '[ACTION] {"forward":1,"sprint":1} x30 -> 30 ticks: moved 4.2')
    assert R.changed(good) and not R.raw_nudge(good)
    stuck = row(21, "forward", 400, 420, '[ACTION] {"forward":1} x20 -> 20 ticks: moved 0.0', tags=["stuck"])
    assert not R.changed(stuck)
