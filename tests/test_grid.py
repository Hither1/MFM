"""The runner's cell map (mcu_worldmodel/grid.py) and the three macros that consume it:
the go_to detour over walked cells, the re-open by replayed pose, and the walk out of
the pond trap along the avatar's own trail. Measured need (2026-09-06 findings):
30-50% of blocked go_to targets never reached, a median 612 steps from the water fill
to the descent, a remembered furnace one cell off for ~10k steps."""
from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from mcu_worldmodel.grid import Grid


def _pos(x, y, z, pitch=0.0, yaw=0.0):
    return {"x": float(x), "y": float(y), "z": float(z), "pitch": float(pitch),
            "yaw": float(yaw)}


def _walk(grid: Grid, cells, step0=0):
    step = step0
    for c in cells:
        grid.observe(step, _pos(c[0] + 0.5, c[1], c[2] + 0.5))
        step += 3
    return step


def _L_trail():
    """East along z=0 from x 0..6, then north along x=6 from z 0..6."""
    return [(x, 64, 0) for x in range(7)] + [(6, 64, z) for z in range(1, 7)]


# ---------------- the map itself ----------------

def test_observe_records_walked_cells_edges_and_floor(tmp_path: Path):
    g = Grid(tmp_path / "grid.jsonl")
    _walk(g, _L_trail())
    assert (0, 64, 0) in g.walked and (6, 64, 6) in g.walked
    assert (3, 63, 0) in g.floor
    assert (1, 64, 0) in g.edges[(0, 64, 0)] and (5, 64, 0) in g.edges[(6, 64, 0)]
    assert len(g.trail) == 13
    # standing still does not grow the trail or the file
    n = g.events
    g.observe(100, _pos(6.4, 64, 6.6))
    assert g.events == n and len(g.trail) == 13


def test_persist_and_reload_round_trip(tmp_path: Path):
    p = tmp_path / "grid.jsonl"
    g = Grid(p)
    _walk(g, _L_trail())
    g.mark_water(40, 10.2, 10.7, 64.0)
    g.mark_hazard(41, _pos(6.5, 64, 6.5), 4.0)
    g.mark_lava(42, (20, 11, 20), (19, 11, 20), 0.5)
    g.mark_placed(43, "crafting_table", (7, 64, 6), _pos(6.5, 64, 6.5, 55, -49))
    g.mark_opened(44, "crafting_table", _pos(6.3, 64, 6.3, 50, -45))
    g.mark_blocked(45, _pos(6.5, 64, 6.5, yaw=0.0))
    h = Grid(p)
    assert h.walked.keys() == g.walked.keys()
    assert h.edges == g.edges and [c for _, c in h.trail] == [c for _, c in g.trail]
    assert h.water == g.water and h.lava == g.lava and h.blocked == g.blocked
    assert h.hazard[(6, 64, 6)]["damage"] == 4.0
    assert h.placed["crafting_table"]["cell"] == (7, 64, 6)
    assert h.opened["crafting_table"]["pose"]["yaw"] == -45.0
    assert h.audit()["walked"] == 13


def test_blocked_cell_is_one_ahead_along_the_yaw():
    g = Grid()
    assert g.mark_blocked(1, _pos(6.5, 64, 6.5, yaw=0.0)) == (6, 64, 7)      # +z
    assert g.mark_blocked(2, _pos(6.5, 64, 6.5, yaw=90.0)) == (5, 64, 6)     # -x
    assert g.mark_blocked(3, _pos(6.5, 64, 6.5, yaw=-90.0)) == (7, 64, 6)    # +x


def test_detour_finds_the_walked_cell_nearest_the_target():
    g = Grid()
    _walk(g, _L_trail())
    # At the north end, wanting (2, 2): straight west is walled; the trail's corner
    # cell (2, 0) is 2 blocks from the target, nearer than here (5.7) by the gain.
    path = g.detour(_pos(6.5, 64, 6.5), 2.5, 2.5)
    assert path and path[-1] == (2, 64, 0)
    assert path[0] == (6, 64, 5)                     # back down the trail first
    assert all(c in g.walked for c in path)
    # Nothing nearer on the trail: no detour.
    assert g.detour(_pos(6.5, 64, 6.5), 6.5, 30.5) is None


def test_escape_from_water_walks_the_trail_back_to_dry_ground():
    g = Grid()
    trail = [(x, 64, 0) for x in range(0, 11)]        # spawn (0,0) to the pond (10,0)
    _walk(g, trail)
    g.mark_water(50, 11.5, 0.5, 64.0)                  # the pond beside the last cell
    path = g.escape_from_water(_pos(10.5, 64, 0.5), 8.0)
    assert path and path[-1] == (3, 64, 0)             # 8 blocks from x=11
    assert [c[0] for c in path] == [9, 8, 7, 6, 5, 4, 3]
    assert g.escape_from_water(_pos(10.5, 64, 0.5), 30.0) is None


def test_summary_names_cell_water_hazard_and_placed_pose():
    g = Grid()
    _walk(g, [(x, 64, 0) for x in range(0, 11)])
    g.mark_water(50, 11.5, 0.5, 64.0)
    g.mark_hazard(51, _pos(9.5, 64, 0.5), 5.0)
    g.mark_placed(52, "furnace", (1, 64, 1), _pos(0.5, 64, 0.5, 55, 0))
    g.mark_opened(53, "furnace", _pos(0.4, 64, 0.6, 52, 3))
    text = g.summary(_pos(10.5, 64, 0.5), 60)
    assert "You stand in cell (10, 64, 0)" in text and "11 cells walked" in text
    assert "WATER 1 blocks away" in text and "dry walked cell nearest you is (3, 64, 0)" in text
    assert "DANGER within 8 blocks: damage at (9, 64, 0)" in text
    assert "furnace: cell (1, 64, 1)" in text and "opened from (0.4, 64, 0.6) pitch 52 yaw 3" in text
    assert "walked route:" in text
    assert g.summary(None, 1) == "" and Grid().summary(_pos(0, 0, 0), 1) == ""


# ---------------- the runner hooks ----------------

def _agent(grid: Grid, pos, tmp_path: Path, pov=None):
    from mcu_worldmodel.agent import WorldModelAgent as A
    notes: list[str] = []
    attach = tmp_path / "attach"
    attach.mkdir(exist_ok=True)
    ns = SimpleNamespace(
        grid=grid, step=500, cursor_stats={}, _cur_pos=dict(pos), _last_pov=pov,
        memory=SimpleNamespace(add_note=notes.append, attach_dir=attach, _pending_notes=[]),
        notes=notes, queue=deque(), DIG_WATER_BLOCKS=A.DIG_WATER_BLOCKS,
        memory_mode="logbook", frame_size=(640, 360), _event_frames=[],
        _recent_outcomes=deque(maxlen=6), _sheet_labels=[])
    ns._keep_event_frame = lambda step, label, pov: A._keep_event_frame(ns, step, label, pov)
    ns._goto_stalled = lambda gt, p, mk: A._goto_stalled(ns, gt, p, mk)
    ns._pose_replay_tick = lambda ug, pose, mk: A._pose_replay_tick(ns, ug, pose, mk)
    ns._queue_water_escape = lambda idx: A._queue_water_escape(ns, idx)
    ns._goto_tick = lambda gt, mk: A._goto_tick(ns, gt, mk)
    ns._event_sheet = lambda info: A._event_sheet(ns, info)
    ns._recent_block = lambda: A._recent_block(ns)
    return ns


def _mk(**kw):
    return {"camera": [0.0, 0.0], **kw}


def test_goto_detours_once_over_walked_cells_then_resumes(tmp_path: Path):
    from mcu_worldmodel.procedures import go_to
    g = Grid()
    _walk(g, _L_trail())
    ag = _agent(g, _pos(6.5, 64, 6.5, yaw=90.0), tmp_path)       # facing -x, the wall
    gt = go_to(x=2.5, z=2.5, within=1.0, n=60)[0]["_goto"]
    acts = []
    for _ in range(12):                                           # walled: no movement
        a = ag._goto_tick(gt, _mk)
        acts.append(a)
        if a is None or gt.get("detoured"):
            break
        ag._cur_pos["yaw"] += a["camera"][1]                      # the turn lands; no walk
    assert all(a is not None for a in acts), "the walk gave up instead of detouring"
    assert gt.get("detoured") and gt["via"] and gt["via"][-1] == (2.5, 0.5)
    assert ag.cursor_stats["goto_detours"] == 1 and (5, 64, 5) in g.blocked   # ahead along the turned yaw
    assert any("detouring over" in n for n in ag.notes)
    # The next tick steers toward the first waypoint (6, 5): due -z from here.
    a = ag._goto_tick(gt, _mk)
    assert a is not None and abs(a["camera"][1]) > 0
    # Arriving at each waypoint pops it; at the last one the target itself is next.
    ag._cur_pos = _pos(2.5, 64, 0.5, yaw=90.0)
    a = ag._goto_tick(gt, _mk)
    assert gt["via"] == [] and a is not None
    ag._cur_pos = _pos(2.5, 64, 2.2, yaw=90.0)
    assert ag._goto_tick(gt, _mk) is None and ag.cursor_stats["goto_detour_arrived"] == 1


def test_goto_stops_with_the_note_when_no_walked_cell_is_nearer(tmp_path: Path):
    from mcu_worldmodel.procedures import go_to
    g = Grid()
    _walk(g, [(6, 64, z) for z in range(0, 7)])
    ag = _agent(g, _pos(6.5, 64, 6.5, yaw=90.0), tmp_path)
    gt = go_to(x=6.5, z=40.5, within=1.0, n=60)[0]["_goto"]
    last = None
    for _ in range(12):
        last = ag._goto_tick(gt, _mk)
        if last is None:
            break
        ag._cur_pos["yaw"] += last["camera"][1]
    assert last is None and not gt.get("detoured")
    assert any("no walked cell lies nearer" in n for n in ag.notes)


def test_pose_replay_walks_sneaks_and_turns_to_the_recorded_pose(tmp_path: Path):
    g = Grid()
    pose = {"x": 6.3, "y": 64.0, "z": 6.3, "pitch": 52.0, "yaw": -45.0}
    ag = _agent(g, _pos(4.5, 64, 6.3, yaw=0.0), tmp_path)
    ug = {"attempts": 4, "item": "crafting_table"}
    for _ in range(200):
        a = ag._pose_replay_tick(ug, pose, _mk)
        if a is None:
            break
        p = ag._cur_pos
        # a crude sim: the camera moves as asked, forward moves 0.2 (0.07 sneaking)
        p["yaw"] += a["camera"][1]
        p["pitch"] += a["camera"][0]
        if a.get("forward"):
            speed = 0.07 if a.get("sneak") else 0.2
            p["x"] += -math.sin(math.radians(p["yaw"])) * speed
            p["z"] += math.cos(math.radians(p["yaw"])) * speed
    st = ug["replay"]
    assert st["phase"] == "done"
    assert math.hypot(ag._cur_pos["x"] - pose["x"], ag._cur_pos["z"] - pose["z"]) <= 0.35
    assert abs(ag._cur_pos["pitch"] - 52.0) <= 1.5 and abs(ag._cur_pos["yaw"] + 45.0) <= 1.5


def test_pose_replay_gives_up_when_walled(tmp_path: Path):
    g = Grid()
    pose = {"x": 9.3, "y": 64.0, "z": 6.3, "pitch": 52.0, "yaw": -45.0}
    ag = _agent(g, _pos(4.5, 64, 6.3, yaw=-90.0), tmp_path)       # facing +x already
    ug = {"attempts": 4, "item": "furnace"}
    n = 0
    while ag._pose_replay_tick(ug, pose, _mk) is not None:       # never moves
        n += 1
        assert n < 200
    assert ug["replay"]["phase"] == "walk" and n <= 12


def test_water_refusal_queues_the_walk_along_the_trail(tmp_path: Path):
    g = Grid()
    _walk(g, [(x, 64, 0) for x in range(0, 11)])
    g.mark_water(50, 11.5, 0.5, 64.0)
    ag = _agent(g, _pos(10.5, 64, 0.5), tmp_path)
    ag.queue.append(({"_dig": {"remaining": 5}}, 0))
    ag._queue_water_escape(0)
    assert len(ag.queue) == 2 and "_goto" in ag.queue[1][0]
    gt = ag.queue[1][0]["_goto"]
    assert gt["x"] == 3.5 and gt["z"] == 0.5 and gt["detoured"] and len(gt["via"]) == 6
    assert ag.cursor_stats["water_escapes"] == 1
    assert any("along your own trail to (3, 64, 0)" in n for n in ag.notes)
    # nothing known: nothing queued, no note
    ag2 = _agent(Grid(), _pos(10.5, 64, 0.5), tmp_path)
    ag2._queue_water_escape(0)
    assert not ag2.queue and not ag2.notes


def test_event_sheet_tiles_the_current_view_and_the_event_frames(tmp_path: Path):
    from PIL import Image
    g = Grid()
    ag = _agent(g, _pos(0, 64, 0), tmp_path)
    assert ag._event_sheet({"pov": np.zeros((360, 640, 3), np.uint8)}) is None
    f1 = np.full((360, 640, 3), 90, np.uint8)
    f2 = np.full((360, 640, 3), 200, np.uint8)
    ag._keep_event_frame(10, "lava", f1)
    ag._keep_event_frame(11, "blocked", f2)
    ag._keep_event_frame(12, "hit", f2)
    ag._keep_event_frame(13, "water", f1)
    assert [l for _, l, _ in ag._event_frames] == ["blocked", "hit", "water"]   # last three
    path = ag._event_sheet({"pov": np.full((360, 640, 3), 30, np.uint8)})
    assert path is not None and path.name == "events.png"
    im = Image.open(path)
    assert im.size == (640, 360)
    px = np.asarray(im)
    assert px[100, 100].tolist() == [30, 30, 30]          # top-left: the current view
    assert px[100, 420].tolist() == [200, 200, 200]       # top-right: "blocked"
    assert px[280, 420].tolist() == [90, 90, 90]          # bottom-right: "water"
    assert ag._event_frames == [] and ag.cursor_stats["event_sheets"] == 1
    assert ag._sheet_labels == ["blocked (step 11)", "hit (step 12)", "water (step 13)"]


def test_recent_block_renders_the_last_entries(tmp_path: Path):
    ag = _agent(Grid(), _pos(0, 64, 0), tmp_path)
    assert ag._recent_block() == ""
    for i in range(8):
        ag._recent_outcomes.append({"step": 100 + i, "label": f"go_to(x={i})", "moved": 0.0,
                                    "descended": 0.0, "inv": "", "events": [],
                                    "note": "blocked" if i % 2 else ""})
    text = ag._recent_block()
    assert text.startswith("[RECENT]") and text.count("\n- step") == 6
    assert "step 102" in text and "step 101" not in text and "note: blocked" in text


def test_grid_file_is_kept_by_the_sweep_and_carried(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory
    from mcu_worldmodel.previous import NOT_CARRIED
    m = MultimodalMemory(tmp_path / "ws", structured=False)
    (m.root / "grid.jsonl").write_text('{"kind":"walked","step":1,"cell":[0,64,0]}\n')
    (m.root / "scratch.md").write_text("x")
    removed = m.sweep_foreign()
    assert "scratch.md" in removed and (m.root / "grid.jsonl").exists()
    assert "grid.jsonl" not in NOT_CARRIED


def test_above_finds_the_rim_of_a_hole():
    g = Grid()
    _walk(g, [(x, 69, 0) for x in range(0, 6)])       # the trail on the surface
    _walk(g, [(6, 64, 0), (7, 64, 0)], step0=50)       # then the floor of a hole
    assert g.above(_pos(7.5, 64, 0.5)) == ((5, 69, 0), 5)
    assert g.above(_pos(2.5, 69, 0.5)) is None         # on the surface: nothing higher
    # the mouth of a shaft 44 blocks up is not a rim (og9 at y 11 under its y 55 trail)
    g2 = Grid()
    g2.observe(1, _pos(-2993.5, 55, -5566.5))
    assert g2.above(_pos(-2992.5, 11, -5561.1)) is None
    assert g.above(_pos(40.5, 64, 0.5)) is None        # far from every walked cell


def test_goto_stall_in_a_hole_queues_the_climb(tmp_path: Path, monkeypatch):
    from mcu_worldmodel import macros_world
    from mcu_worldmodel.agent import WorldModelAgent as A
    g = Grid()
    _walk(g, [(x, 69, 0) for x in range(0, 6)])
    _walk(g, [(6, 64, 0), (7, 64, 0)], step0=50)
    ag = _agent(g, _pos(7.5, 64, 0.5, yaw=90), tmp_path)
    ag.cursor = None
    ag._cur_info = {}
    ag._queue_pit_climb = lambda gt, p, up: A._queue_pit_climb(ag, gt, p, up)
    monkeypatch.setattr(macros_world, "pillar_up",
                        lambda cur, info, n=3, item=None: ([{"_pillar": {"target": n}}], "ok"))
    gt = {"x": 0.5, "z": 0.5, "within": 1.0, "remaining": 100, "stuck": 3}
    ag.queue.append(({"_goto": gt}, 0))
    assert ag._goto_stalled(gt, ag._cur_pos, _mk) is None          # the stalled walk ends
    assert gt["pit_climbed"] and ag.cursor_stats["pit_climbs"] == 1
    assert [list(e[0])[0] for e in ag.queue] == ["_goto", "_pillar", "_goto"]
    assert ag.queue[1][0]["_pillar"]["target"] == 5 and ag.queue[2][0]["_goto"]["pit_climbed"]
    assert any("5 blocks below the cell (5, 69, 0)" in n and "pillar_up(5)" in n for n in ag.notes)
    # once climbed, a second stall of the re-queued walk falls through to the plain note
    gt2 = ag.queue[2][0]["_goto"]
    ag.queue.clear(); ag.notes.clear()
    assert ag._goto_stalled(gt2, ag._cur_pos, _mk) is None
    assert not ag.queue and any("is blocked at" in n for n in ag.notes)
    # no block to place: the note says so, nothing queued
    monkeypatch.setattr(macros_world, "pillar_up",
                        lambda cur, info, n=3, item=None: ([], "pillar_up: you carry no placeable block."))
    gt3 = {"x": 0.5, "z": 0.5, "within": 1.0, "remaining": 100, "stuck": 3}
    ag.queue.clear(); ag.notes.clear()
    assert ag._goto_stalled(gt3, ag._cur_pos, _mk) is None
    assert not ag.queue and any("no placeable block" in n and "stair_up" in n for n in ag.notes)
