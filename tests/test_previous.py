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
import sys
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
    lives.seed([a, b], sites=False)
    assert len(lives.lives) == 2, "the shared ancestor was carried twice"
    assert [p.name for p in lives.lives] == ["life_1", "life_2"]


def test_the_record_travels_and_the_machinery_does_not(tmp_path):
    a = _life(tmp_path / "a", "ancestor\n")
    lives = previous.PreviousLives(tmp_path / "ws")
    lives.seed([a], sites=False)
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
    lives.seed([a, b], sites=False)
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
    lives.seed([a], sites=False)
    assert lives.rows == []
    assert not (tmp_path / "ws" / "previous" / "index.jsonl").exists()
    assert (tmp_path / "ws" / "previous" / "life_1" / "logs.txt").exists()


def test_sites_are_the_push_and_are_off_unless_asked(tmp_path):
    a = _life(tmp_path / "a", "one\n")
    off = previous.PreviousLives(tmp_path / "off")
    off.seed([a], sites=False)
    assert not (tmp_path / "off" / "previous" / "sites.json").exists()
    assert off.pushed_sites is False
    on = previous.PreviousLives(tmp_path / "on")
    on.seed([a], sites=True)
    assert (tmp_path / "on" / "previous" / "sites.json").exists()
    assert on.pushed_sites is True
