"""Characterization of MCU's carry layer (`mcu_worldmodel/previous.py: PreviousLives`).

Recorded before `mfm/memory/carry.py` and this module were given one shared spine, so
the refactor can be checked against what the code did rather than against what it was
meant to do: this layer had no test of its own.

What it fixes: which lives a set of seeds expands to and in what order, the dedup rule
(a life is its log's bytes, so a life carried by two seeds is carried once), what is and
is not linked into `previous/life_<i>/`, and the merged `previous/index.jsonl` -- one row
per carried episode, stamped with its life and with every path rewritten to point inside
the carried tree.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import MCU  # noqa: F401  (puts the MCU checkout on sys.path)

previous = pytest.importorskip("mcu_worldmodel.previous")


def _life(root: Path, log: str, *, episodes: bool = True) -> Path:
    """A finished run's memory dir: its record, plus machinery that must not travel."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs.txt").write_text(log, encoding="utf-8")
    (root / "grid.jsonl").write_text('{"cell": [1, 2, 3]}\n', encoding="utf-8")
    (root / "notes.md").write_text("what the model wrote\n", encoding="utf-8")
    if episodes:
        ep = root / "episodes" / "ep_000001"
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "state.json").write_text("{}", encoding="utf-8")
        (root / "index.jsonl").write_text(json.dumps(
            {"step": 7, "path": "episodes/ep_000001",
             "image": "frames/step_0007.png"}, sort_keys=True) + "\n", encoding="utf-8")
    # machinery: the contract, the tools, the per-turn attachment, a site digest
    (root / "AGENTS.md").write_text("the contract", encoding="utf-8")
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "episodes.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (root / "attach").mkdir(exist_ok=True)
    (root / "attach" / "events.png").write_bytes(b"\x89PNG")
    (root / "sites.json").write_text("{}", encoding="utf-8")
    return root


def test_lives_of_expands_a_seed_oldest_first(tmp_path):
    seed = _life(tmp_path / "seed", "seed run\n")
    carried = _life(seed / "previous" / "life_1", "an ancestor\n")
    assert previous.lives_of(seed) == [carried, seed]


def test_a_life_is_its_log_bytes_so_a_shared_ancestor_carries_once(tmp_path):
    a = _life(tmp_path / "a", "ancestor\n")
    b = _life(tmp_path / "b", "b run\n")
    _life(b / "previous" / "life_1", "ancestor\n")        # the same life, carried by b
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a, b])
    assert len(lives.lives) == 2, "the shared ancestor was carried twice"
    assert [p.name for p in lives.lives] == ["life_1", "life_2"]


def test_the_record_travels_and_the_machinery_does_not(tmp_path):
    a = _life(tmp_path / "a", "ancestor\n")
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a])
    life = tmp_path / "ws" / "previous" / "life_1"
    for kept in ("logs.txt", "grid.jsonl", "notes.md", "index.jsonl",
                 "episodes/ep_000001/state.json"):
        assert (life / kept).exists(), f"{kept} should have been carried"
    for dropped in ("AGENTS.md", "tools/episodes.py", "attach/events.png", "sites.json"):
        assert not (life / dropped).exists(), f"{dropped} is machinery, not record"
    assert lives.linked == 5


def test_the_merged_index_stamps_the_life_and_rewrites_every_path(tmp_path):
    a, b = _life(tmp_path / "a", "one\n"), _life(tmp_path / "b", "two\n")
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a, b])
    rows = [json.loads(l) for l in
            (tmp_path / "ws" / "previous" / "index.jsonl").read_text().splitlines() if l.strip()]
    assert [r["life"] for r in rows] == [1, 2]
    assert [r["path"] for r in rows] == ["previous/life_1/episodes/ep_000001",
                                         "previous/life_2/episodes/ep_000001"]
    assert rows[0]["image"] == "previous/life_1/frames/step_0007.png"
    assert lives.rows == rows


def test_a_life_without_a_store_contributes_no_rows(tmp_path):
    a = _life(tmp_path / "a", "one\n", episodes=False)
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a])
    assert lives.rows == []
    assert not (tmp_path / "ws" / "previous" / "index.jsonl").exists()
    assert (tmp_path / "ws" / "previous" / "life_1" / "logs.txt").exists()
    assert not (tmp_path / "ws" / "previous" / "scripts.md").exists(), "no script, no table"


def test_the_scripts_table_counts_calls_refusals_and_firings(tmp_path):
    """`previous/scripts.md`: each earlier script with its calls (index rows of its
    name), its guard's refusals (the FAILED notes) and the last outcome; a reflex with
    its firings. Counted from the record, not judged."""
    a = _life(tmp_path / "a", "\n".join([
        "[NOTE] shaft_down (mine/procedures/shaft_down.py) FAILED, nothing ran: exit code 1: not standing on solid ground (y 21.16)",
        "[NOTE] [REFLEX lava_ahead] lava fills 3% of the lower view during mine_ahead -- stepped back 6 ticks",
        "[NOTE] [REFLEX lava_ahead] lava fills 5% of the lower view at a look -- stopped",
        ""]))
    (a / "mine" / "procedures").mkdir(parents=True)
    (a / "mine" / "reflexes").mkdir(parents=True)
    (a / "mine" / "procedures" / "shaft_down.py").write_text("# a script\n")
    (a / "mine" / "procedures" / "stair_up.py").write_text("# never called\n")
    (a / "mine" / "reflexes" / "lava_ahead.py").write_text("# a reflex\n")
    (a / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
        {"kind": "episode", "action_kind": "shaft_down", "first_step": 100, "path": "episodes/ep_000001",
         "summary": "[ACTION] shaft_down(target_y=13) -> 370 ticks: moved 0.0, y 24 -> 13"},
        {"kind": "episode", "action_kind": "look_abs", "first_step": 500, "path": "episodes/ep_000002",
         "summary": "[ACTION] look_abs(pitch=60) -> 8 ticks"},
        {"kind": "episode", "action_kind": "shaft_down", "first_step": 900, "path": "episodes/ep_000003",
         "summary": "[ACTION] shaft_down(target_y=12) -> 41 ticks: moved 0.0, lava below"}]))
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a])
    table = (tmp_path / "ws" / "previous" / "scripts.md").read_text()
    assert "## life_1" in table
    assert "| `shaft_down` | 2 | 1 | step 900: 41 ticks: moved 0.0, lava below; last refusal: exit code 1: not standing on solid ground (y 21.16) |" in table
    assert "| `stair_up` | 0 | 0 | never called |" in table
    assert "| `lava_ahead` | 2 | lava fills 5% of the lower view at a look -- stopped |" in table

