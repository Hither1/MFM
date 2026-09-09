"""`mfm.memory.retrieve.recall_block`: the three questions it answers, on rows shaped
like the store's index, and its silence when there is nothing to recall."""
from __future__ import annotations

import json
from pathlib import Path

from mfm.memory import retrieve as R


def _row(i: int, kind: str, first: int, last: int, *, tags=(), x=0.0, z=0.0,
         summary: str | None = None, kind_="episode") -> dict:
    return {"id": f"ep_{i:06d}", "kind": kind_, "action_kind": kind, "first_step": first,
            "last_step": last, "tags": list(tags), "x": x, "y": 64.0, "z": z,
            "path": f"episodes/ep_{i:06d}",
            "summary": summary or f"[ACTION] {kind}() -> {last - first} ticks: moved 0.0"}


def _write_outcome(root: Path, row: dict, notes: list[str]) -> None:
    d = root / row["path"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "outcome.json").write_text(json.dumps({"notes": notes, "tags": row["tags"]}))


def test_empty_index_is_silent():
    assert R.recall_block([], pos=(0.0, 0.0)) == ""
    assert R.recall_block([_row(0, None, 0, 0, tags=["initial"], kind_="initial")]) == ""


def test_streak_names_the_run_its_note_and_the_last_success(tmp_path: Path):
    rows = [_row(0, None, 0, 0, tags=["initial"], kind_="initial"),
            _row(1, "harvest_tree", 10, 200, tags=["inventory_changed"],
                 summary="[ACTION] harvest_tree(logs=4) -> 190 ticks: moved 2.0, inv {'oak_log': 4}"),
            _row(2, "craft", 200, 201, tags=["inventory_changed"]),
            _row(3, "harvest_tree", 300, 400, x=1, z=1),
            _row(4, "dirt_pickup", 400, 410, tags=["inventory_changed"]),   # a change in between
            _row(5, "harvest_tree", 500, 600, x=8, z=8),
            _row(6, "harvest_tree", 700, 800, x=8, z=9)]
    _write_outcome(tmp_path, rows[6], ["harvest_tree: no trunk detected (6 frames). Turn "
                                       "toward visible LEAVES and retry", "second note"])
    # three calls make a streak only when asked for (the default asks for four since
    # 2026-09-09: of3g's prompts carried an entry-grain line 169 turns out of 229)
    assert "changed nothing" not in R.recall_block(rows, tmp_path, pos=(100.0, 100.0))
    block = R.recall_block(rows, tmp_path, pos=(100.0, 100.0), streak_min=3)
    assert block.startswith("[RECALL]")
    assert "`harvest_tree` changed nothing in its last 3 calls (since step 300, 3 spots" in block
    assert 'ep_000006, steps 700-800): "harvest_tree: no trunk detected (6 frames)' in block
    assert "It last changed something at step 10 (ep_000001: harvest_tree(logs=4))." in block
    # Two failures are not a streak, and the changed entries are not one either.
    assert "`craft`" not in block and "dirt_pickup" not in block
    assert "Here before" not in block          # nothing near (100, 100)


def test_streak_without_any_success_says_so_and_ignores_bookkeeping():
    rows = [_row(i, "look_abs", i * 10, i * 10 + 1) for i in range(1, 6)]
    rows += [_row(10 + i, "dig_down", 100 + i * 10, 105 + i * 10, tags=["stuck"]) for i in range(4)]
    block = R.recall_block(rows, ignore_kinds={"look_abs"})
    assert "`look_abs`" not in block
    assert "`dig_down` changed nothing in its last 4 calls" in block
    assert "It has never changed anything." in block
    assert R.streaks(rows, min_len=5, ignore={"look_abs"}) == []


def test_stale_streak_is_history_not_a_loop():
    rows = [_row(i, "stow_items", i * 10, i * 10 + 1) for i in range(1, 4)]
    rows += [_row(10 + i, "strip_mine", 100 + i * 10, 105 + i * 10, tags=["inventory_changed"])
             for i in range(40)]
    assert R.streaks(rows) == []                       # the run ended 40 rows ago
    assert [s["kind"] for s in R.streaks(rows, recent=0)] == ["stow_items"]
    assert R.recall_block(rows) == ""


def test_movers_count_arriving_as_a_change():
    rows = [_row(i, "go_to", i * 10, i * 10 + 5, tags=["stuck"] if i % 2 else ())
            for i in range(1, 7)]
    assert R.streaks(rows, movers={"go_to"}) == []     # every other call arrived
    rows += [_row(10 + i, "go_to", 100 + i * 10, 105 + i * 10, tags=["stuck"]) for i in range(3)]
    assert R.streaks(rows) [0]["n"] == 9               # without movers: nothing ever "changed"
    s = R.streaks(rows, movers={"go_to"})[0]
    assert s["n"] == 3 and s["last_success"]["id"] == "ep_000006"


def test_repeated_note_chain(tmp_path: Path):
    dark = ("{k}: broke {n} blocks, descended {n}.0 in 360 ticks. The view was DARK throughout "
            "(mean brightness {n}/255): the ore watch cannot see ore colours in the dark, so "
            "this stretch found none. Craft torches first.")
    rows = [_row(1, "dig_down", 10, 20, tags=["inventory_changed"])]
    _write_outcome(tmp_path, rows[0], ["dig_down: fine"])
    for i, k in enumerate(("dig_down", "strip_mine", "look_abs", "strip_mine", "mine_forward"), 2):
        r = _row(i, k, i * 100, i * 100 + 50, tags=["inventory_changed"])
        rows.append(r)
        _write_outcome(tmp_path, r, [] if k == "look_abs" else [dark.format(k=k, n=i * 3)])
    chain = R.repeated_note(rows, tmp_path)
    assert chain and chain["n"] == 4 and chain["since_step"] == 200
    assert chain["kinds"] == {"strip_mine": 2, "dig_down": 1, "mine_forward": 1}
    block = R.recall_block(rows, tmp_path, streak_min=99)
    assert ("- The same harness note ended the last 4 entries that carried one (since step "
            "200; strip_mine x2, dig_down x1, mine_forward x1): \"The view was DARK throughout "
            "(mean brightness 18/255): the ore watch cannot see ore colours in the dark, so this "
            "stretch found none.\"" in block), block
    # Three different notes: no chain. Fewer than min_len: no chain.
    for r in rows[1:]:
        _write_outcome(tmp_path, r, [f"{r['action_kind']}: something else happened at {r['id']}"])
    assert R.repeated_note(rows, tmp_path) is None
    assert R.repeated_note(rows[:2], tmp_path) is None


def test_openers_change_something_only_when_a_screen_opened():
    rows = [_row(i, "use_until_gui", i * 50, i * 50 + 30) for i in range(1, 6)]
    assert R.streaks(rows, ignore={"use_until_gui"}) == []          # bookkeeping when ignored
    s = R.streaks(rows, openers={"use_until_gui"})
    assert [x["kind"] for x in s] == ["use_until_gui"] and s[0]["n"] == 5
    rows[2]["tags"] = ["gui"]                                      # the third one opened a screen
    assert R.streaks(rows, openers={"use_until_gui"}) == []        # two failures since: no streak
    s = R.streaks(rows, openers={"use_until_gui"}, min_len=2)
    assert s[0]["n"] == 2 and s[0]["last_success"]["id"] == "ep_000003"


def test_entries_that_never_ran_do_not_make_a_streak():
    # five deferred crafts (zero ticks, nothing changed) around one real harvest_tree failure
    rows = [_row(i, "craft", 100 + i, 100 + i) for i in range(1, 6)]
    rows.append(_row(9, "harvest_tree", 200, 400))
    assert R.streaks(rows) == []
    rows += [_row(10 + i, "harvest_tree", 500 + i * 100, 550 + i * 100) for i in range(2)]
    assert [s["kind"] for s in R.streaks(rows)] == ["harvest_tree"]
    # a one-tick entry that DID change something still counts as a success
    rows.append(_row(20, "craft", 900, 900, tags=["inventory_changed"]))
    assert R.streaks(rows, min_len=1)[0]["kind"] == "harvest_tree"


def test_here_before_excludes_the_visible_tail_and_cites_what_changed():
    rows = [_row(1, "dig_down", 10, 20, tags=["stuck"], x=5, z=5),
            _row(2, "craft", 20, 21, tags=["inventory_changed"], x=5, z=6,
                 summary="[ACTION] craft(item=planks,count=1) -> 1 ticks: moved 0.0, inv {'planks': 4}"),
            _row(3, "dig_down", 30, 40, tags=["stuck"], x=5.4, z=5)]
    rows += [_row(10 + i, "walk", 100 + i, 101 + i, x=5, z=5) for i in range(6)]  # the tail
    block = R.recall_block(rows, pos=(5.0, 5.0), streak_min=99)
    assert "Here before (within 6 blocks): 3 episodes, steps 10-40: dig_down x2, craft x1; 1 changed something, 2 stuck." in block
    # since 2026-09-08 the cite carries a bearing from `pos` ("ep_000002 step 20, 3 blocks N: ...")
    assert "ep_000002 step 20, " in block
    assert "craft(item=planks,count=1) -> moved 0.0, inv {'planks': 4}" in block
    assert "walk" not in block
    assert R.here_before(rows, (50.0, 50.0)) == []
    assert R.recall_block(rows, pos=None, streak_min=99) == ""


def test_milestone_recipe_index():
    rows = [_row(1, "attack", 300, 366, tags=["milestone", "inventory_changed"],
                 summary='[ACTION] {"attack":1} x110 -> 110 ticks: moved 0.0, inv {\'spruce_log\': 1}, milestone [\'mine_log\']'),
            _row(2, "craft", 562, 562, tags=["milestone", "inventory_changed"],
                 summary="[ACTION] craft(item=crafting_table,count=1) -> 1 ticks: moved 0.0, inv {'crafting_table': 1}, milestone ['crafting_table']")]
    assert "Milestones so far" not in R.recall_block(rows)      # off by default (2026-09-08)
    block = R.recall_block(rows, max_milestones=10)
    assert ("- Milestones so far, with the entry that scored each: mine_log step 300 "
            '(ep_000001: {"attack":1} x110); crafting_table step 562 '
            "(ep_000002: craft(item=crafting_table,count=1))." in block)


def _write_delta(root: Path, row: dict, delta: dict, events=()):
    d = root / row["path"]; d.mkdir(parents=True, exist_ok=True)
    (d / "outcome.json").write_text(json.dumps({"inventory_delta": delta, "events": list(events),
                                                "notes": [], "tags": row["tags"]}))


def test_left_behind_tracks_placements_and_pickups(tmp_path: Path):
    rows = [_row(1, "craft", 500, 501, tags=["inventory_changed"], x=-3005, z=-5567,
                 summary="[ACTION] craft(item=crafting_table,count=1) -> 1 ticks: moved 0.0, inv {'crafting_table': 1}"),
            _row(2, "place_and_open", 571, 631, tags=["inventory_changed"], x=-3005, z=-5567,
                 summary="[ACTION] place_and_open(item=crafting_table) -> 60 ticks: moved 0.0, inv {'crafting_table': -1}"),
            _row(3, "dig_down", 700, 900, tags=["inventory_changed"], x=-3005, z=-5567,
                 summary="[ACTION] dig_down(n=200) -> 200 ticks: moved 0.0, inv {'cobblestone': 9}")]
    for r in rows: r["y"] = 68.0
    _write_delta(tmp_path, rows[0], {"crafting_table": 1}, ["craft_item crafting_table +1"])
    _write_delta(tmp_path, rows[1], {"crafting_table": -1})
    _write_delta(tmp_path, rows[2], {"cobblestone": 9})
    out = R.left_behind(rows, tmp_path)
    assert [(p["item"], p["id"], p["step"], p["y"]) for p in out] == [("crafting_table", "ep_000002", 571, 68.0)]
    # a pickup (a gain with no craft event) closes it; a second craft does not
    rows.append(_row(4, "mine_ahead", 950, 990, tags=["inventory_changed"], x=-3005, z=-5567,
                     summary="[ACTION] mine_ahead(n=40) -> 40 ticks: moved 0.0, inv {'crafting_table': 1}"))
    _write_delta(tmp_path, rows[3], {"crafting_table": 1})
    assert R.left_behind(rows, tmp_path) == []
    assert R.left_behind(rows, None) == []


def test_cli_lists_the_outcome_note(tmp_path: Path):
    from mfm.memory.tools import episodes as cli
    rows = [_row(1, "harvest_tree", 10, 20), _row(2, "craft", 20, 21, tags=["inventory_changed"])]
    (tmp_path / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    _write_outcome(tmp_path, rows[0], ["harvest_tree: no trunk detected"])
    _write_outcome(tmp_path, rows[1], [])
    import io, contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(["--root", str(tmp_path), "--last", "2"])
    lines = out.getvalue().splitlines()
    assert "note: harvest_tree: no trunk detected" in lines[0] and "note:" not in lines[1]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(["--root", str(tmp_path), "--last", "1", "--action", "harvest_tree", "--json"])
    assert json.loads(out.getvalue())["note"] == "harvest_tree: no trunk detected"
