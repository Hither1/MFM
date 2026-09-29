"""Plan-grain recall (2026-09-09): the run of turns that re-issued the same EXPECT while
nothing moved, and the hotbar noise that must not be reported as a loop.

Evidence: the six full-task lives of1/of2/of3 and their reuse lives showed the model
re-issuing one [PLAN]/EXPECT for 15-30 turns with moved=0, while the only thing the
[RECALL] block had to say was that `hotbar.6` had changed nothing in its last 61 calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from mfm.memory import retrieve as R


def _row(i: int, kind: str, first: int, last: int, *, moved: float = 0.0, tags=()) -> dict:
    return {"id": f"ep_{i:06d}", "kind": "episode", "action_kind": kind,
            "first_step": first, "last_step": last, "tags": list(tags),
            "x": 0.0, "y": 64.0, "z": 0.0, "path": f"episodes/ep_{i:06d}",
            "image": f"episodes/ep_{i:06d}/observation/image.png",
            "summary": f"[ACTION] {kind}() -> {last - first} ticks: moved {moved:.1f}"}


def _write_action(root: Path, row: dict, turn: int, plan: str | None = None) -> None:
    d = root / row["path"]
    d.mkdir(parents=True, exist_ok=True)
    obj = {"turn": turn, "first_step": row["first_step"]}
    if plan is not None:
        obj["plan"] = plan
        obj["briefing"] = "OBSERVED vs EXPECTED: no change."
    (d / "action.json").write_text(json.dumps(obj), encoding="utf-8")


PLAN = ("Dig forward through the stone face toward the vein.\n\n"
        "EXPECT: the face opens and iron_ore comes into view; health unchanged.")


def _life(root: Path, n_turns: int, *, moved: float = 0.0, plan: str = PLAN,
          tags_per_turn=()) -> list[dict]:
    """`n_turns` turns of two entries each, all issuing the same plan."""
    rows = []
    for t in range(1, n_turns + 1):
        for j in range(2):
            i = 2 * t + j
            r = _row(i, "mine_ahead" if j else "look_abs", 100 * t + 10 * j,
                     100 * t + 10 * j + 5, moved=moved if j else 0.0,
                     tags=tags_per_turn[t - 1] if t - 1 < len(tags_per_turn) else ())
            _write_action(root, r, t, plan if j == 0 else None)
            rows.append(r)
    return rows


def test_three_turns_of_the_same_expect_with_nothing_moving_is_reported(tmp_path: Path):
    rows = _life(tmp_path, 3)
    turns = R.turns_of(rows, tmp_path)
    assert [t["turn"] for t in turns] == [1, 2, 3]
    assert turns[0]["expect"].startswith("the face opens and iron_ore")
    run = R.plan_repeats(turns)
    assert run is not None and run["n"] == 3 and run["source"] == "EXPECT"
    assert run["first_turn"] == 1 and run["last_turn"] == 3
    line = R.plan_repeat_line(run, tmp_path)
    assert line.startswith("The same EXPECT 3 turns running (turns 1-3, steps 100-315)")
    assert "moved=0.0 and no inventory change" in line
    assert "the face opens and iron_ore comes into view" in line
    assert line.endswith("Latest frame: episodes/ep_000007/observation/image.png")
    # the block's first line is the outcome-based stall (plan_stall): three turns of nothing,
    # and it notices the text repeated
    block = R.recall_block(rows, tmp_path, pos=(0.0, 0.0))
    first = block.splitlines()[1]
    assert first.startswith("- Nothing happened for 3 turns (turns 1-3, steps 100-315): moved=0.0, no inventory change")
    assert "the same EXPECT each time (numbers aside)" in first and "Latest EXPECT: `the face opens" in first
    # two turns are not a repeat
    assert R.plan_repeats(R.turns_of(_life(tmp_path / "b", 2), tmp_path / "b")) is None


def test_a_repeat_that_is_getting_somewhere_is_not_reported(tmp_path: Path):
    moving = tmp_path / "moving"
    rows = _life(moving, 4, moved=3.0)
    assert R.plan_repeats(R.turns_of(rows, moving)) is None
    banking = tmp_path / "banking"
    rows = _life(banking, 4, tags_per_turn=[(), (), ("inventory_changed",), ()])
    # the run stops at turn 3, which banked something: one turn left, not a stall
    assert R.plan_repeats(R.turns_of(rows, banking)) is None
    assert R.plan_repeats(R.turns_of(rows, banking), min_len=1)["n"] == 1
    # a plan with no EXPECT line falls back to the plan text
    plain = tmp_path / "plain"
    rows = _life(plain, 3, plan="Dig forward through the stone face toward the vein.")
    run = R.plan_repeats(R.turns_of(rows, plain))
    assert run is not None and run["source"] == "PLAN" and run["n"] == 3
    # rows with no action.json at all say nothing
    assert R.turns_of(rows, None) == [] and R.plan_repeats([]) is None


def test_a_hotbar_streak_is_not_a_loop():
    rows = [_row(i, "hotbar.6", 10 * i, 10 * i + 4) for i in range(1, 9)]
    rows += [_row(20 + i, "equip_hotbar", 300 + 10 * i, 304 + 10 * i) for i in range(4)]
    assert all(R.hotbar_only(r["action_kind"]) for r in rows)
    assert R.hotbar_only("forward+hotbar.3") is False and R.hotbar_only("mine_ahead") is False
    assert R.streaks(rows, min_len=3) == []
    assert R.recall_block(rows) == ""
    # a real kind in the same run still is one
    rows += [_row(40 + i, "mine_ahead", 500 + 10 * i, 505 + 10 * i) for i in range(3)]
    assert [s["kind"] for s in R.streaks(rows, min_len=3)] == ["mine_ahead"]


def test_plan_stall_is_outcome_based_and_flags_a_long_dead_plan(tmp_path: Path):
    """The record's real shape (worker_recall_2026-09-09.md): EXPECT lines rephrased every
    turn with the numbers changed, and single plans of 15-24 entries that achieve nothing."""
    # three turns, three different EXPECT texts, nothing moved: a stall all the same
    root = tmp_path / "rephrased"
    rows = []
    for t in range(1, 4):
        for j in range(2):
            i = 2 * t + j
            r = _row(i, "mine_ahead" if j else "look_abs", 100 * t + 10 * j, 100 * t + 10 * j + 5)
            _write_action(root, r, t, f"Mine two blocks west.\n\nEXPECT: x reaches -310{t}.{t} and the face opens." if j == 0 else None)
            rows.append(r)
    turns = R.turns_of(rows, root)
    assert R.plan_repeats(turns) is None                       # not the same text
    st = R.plan_stall(turns)
    assert st is not None and st["n"] == 3 and st["same_text"] and not st["long_plan"]
    line = R.plan_stall_line(st)
    assert line.startswith("Nothing happened for 3 turns") and "numbers aside" in line
    # one turn whose plan ran 14 entries to no effect is reported alone
    root2 = tmp_path / "long"
    rows2 = []
    for j in range(14):
        r = _row(j, "mine_ahead", 500 + 10 * j, 505 + 10 * j)
        _write_action(root2, r, 7, PLAN if j == 0 else None)
        rows2.append(r)
    st2 = R.plan_stall(R.turns_of(rows2, root2))
    assert st2 is not None and st2["n"] == 1 and st2["entries"] == 14 and st2["long_plan"]
    assert R.plan_stall_line(st2).startswith("Your last plan ran 14 entries (steps 500-635) and changed nothing")
    # a short plan of one quiet turn says nothing; a turn that moved ends the run
    assert R.plan_stall(R.turns_of(rows2[:5], root2)) is None
    moving = tmp_path / "moving"
    assert R.plan_stall(R.turns_of(_life(moving, 4, moved=3.0), moving)) is None
