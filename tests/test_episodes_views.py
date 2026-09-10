"""The two views added to the workspace query tool (2026-09-09): `--ores` (where ore was
seen, and at what y) and `--y-profile` (where the agent has already looked). Both on a
tiny synthetic index, both with and without `--previous`."""
from __future__ import annotations

import json
from pathlib import Path

from mfm.memory.tools import episodes as T


def _write(root: Path, rows: list[dict], outcomes: dict[str, dict], previous: bool = False) -> None:
    d = root / "previous" if previous else root
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for r in rows:
        p = root / r["path"]
        p.mkdir(parents=True, exist_ok=True)
        (p / "outcome.json").write_text(json.dumps(outcomes.get(r["id"], {})), encoding="utf-8")


def _row(i: int, step: int, span: int, y: float, **extra) -> dict:
    return {"id": f"ep_{i:06d}", "kind": "episode", "first_step": step,
            "last_step": step + span, "tags": [], "x": 10.0, "y": y, "z": -20.0,
            "path": extra.pop("path", f"episodes/ep_{i:06d}"),
            "image": extra.pop("image", f"episodes/ep_{i:06d}/observation/image.png"),
            "summary": "[ACTION] mine_ahead(n=10) -> 10 ticks: moved 0.0", **extra}


def test_ores_lists_where_ore_was_seen_and_y_profile_counts_where_it_looked(tmp_path, capsys):
    rows = [_row(1, 100, 50, 70.0), _row(2, 200, 40, 12.0), _row(3, 300, 60, 12.0),
            _row(4, 400, 30, 11.0), _row(5, 500, 0, 11.0)]
    outcomes = {
        "ep_000002": {"events": ["mine_block deepslate_iron_ore +1", "use_item stone_pickaxe +1"],
                      "inventory_delta": {}},
        "ep_000003": {"events": ["pickup dirt +1"], "inventory_delta": {"raw_iron": 1, "diamond_ore": 2}},
        "ep_000004": {"events": ["craft_item iron_ingot +1"], "inventory_delta": {}},
        "ep_000001": {"events": ["mine_block spruce_log +1"], "inventory_delta": {"spruce_log": 1}},
    }
    _write(tmp_path, rows, outcomes)

    assert T.main(["--root", str(tmp_path), "--ores"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2                                    # the log and the smelt are not ore
    assert out[0].startswith("ep_000002  step 200  y=12  pos=(10,12,-20)")
    assert "mine_block deepslate_iron_ore +1" in out[0]
    assert out[0].endswith("-> episodes/ep_000002/observation/image.png")
    assert "inventory diamond_ore +2" in out[1] and "raw_iron" not in out[1]

    assert T.main(["--root", str(tmp_path), "--y-profile"]) == 0
    out = capsys.readouterr().out
    assert "[this life] 180 steps over 3 y bands of 4" in out
    assert "y   68..71        50 steps" in out
    assert "y   12..15       100 steps" in out               # two episodes at y=12
    assert "y    8..11        30 steps" in out               # the zero-length one contributes nothing
    # the filters still apply, and so does the band size
    assert T.main(["--root", str(tmp_path), "--y-profile", "--steps", "190", "350", "--band", "16"]) == 0
    out = capsys.readouterr().out
    assert "[this life] 100 steps over 1 y bands of 16" in out and "y    0..15" in out


def test_both_views_read_the_carried_lives(tmp_path, capsys):
    prev = [_row(9, 700, 20, 63.0, path="previous/life_1/episodes/ep_000009",
                 image="previous/life_1/episodes/ep_000009/observation/image.png", life=1),
            _row(8, 800, 40, 9.0, path="previous/life_2/episodes/ep_000008",
                 image="previous/life_2/episodes/ep_000008/observation/image.png", life=2)]
    _write(tmp_path, prev, {"ep_000009": {"events": ["mine_block coal_ore +3"]}}, previous=True)
    (tmp_path / "index.jsonl").write_text("", encoding="utf-8")

    assert T.main(["--root", str(tmp_path), "--ores", "--previous"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and "life 1" in out[0] and "mine_block coal_ore +3" in out[0]
    assert out[0].endswith("-> previous/life_1/episodes/ep_000009/observation/image.png")

    assert T.main(["--root", str(tmp_path), "--y-profile", "--previous"]) == 0
    out = capsys.readouterr().out
    assert "[life 1] 20 steps" in out and "[life 2] 40 steps" in out


def test_the_existing_listing_is_unchanged(tmp_path, capsys):
    rows = [_row(1, 100, 50, 70.0)]
    _write(tmp_path, rows, {"ep_000001": {"notes": ["mine_ahead: finished 10 ticks."]}})
    assert T.main(["--root", str(tmp_path), "--last", "5"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("ep_000001  steps 100-150  tags=- pos=(10.0,-20.0)  action=-")
    assert out.endswith("note: mine_ahead: finished 10 ticks.  -> episodes/ep_000001/")
