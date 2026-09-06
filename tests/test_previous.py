"""The mfm arm's carried lives (mcu_worldmodel/previous.py): what a seed brings under
previous/, the sites read from its log, the order the [KNOWN SITES] block puts them in,
and that the chassis keeps and announces them."""
from __future__ import annotations

import json
from pathlib import Path

SEP = "=" * 80

LOG = f"""{SEP}
Action 0 | Step 0 | INITIAL STATE

Task: test
[STATE] pos=(-3009.50, 71.00, -5572.50) pitch=0 yaw=0 moved=0.00
{SEP}
Action 5 | Step 543 | Plan Step 2/4 | 13/24 verified

[ACTION] fetch_water(n=120) -> 250 ticks
[STATE] pos=(-3012.10, 70.00, -5578.40) pitch=25 yaw=170 moved=8.10
[NOTE] fetch_water: water reached at (-3013, 70, -5580) after 44 ticks and 9 blocks (the water fills 30% of the lower-centre view).
{SEP}
Action 9 | Step 4359 | Plan Step 1/3 | 13/24 verified

[ACTION] strip_mine(length=250) -> 250 ticks
[STATE] pos=(-3024.30, 54.00, -5552.70) pitch=8 yaw=90 moved=12.00
[EVENT] mine_block iron_ore +1
[EVENT] mine_block stone +9
[NOTE] the runner stopped: iron-ore-like speckles.
{SEP}
Action 74 | Step 4532 | Plan Step 1/2 | 13/24 verified

[ACTION] strip_mine(length=250,ore_watch=True) -> 250 ticks
[STATE] pos=(-2991.40, 11.00, -5561.20) pitch=8 yaw=720 moved=3.00
[NOTE] LAVA AHEAD: 33% of the lower view is lava at (-2991, 11, -5561) facing yaw 720. The runner dropped the rest of your plan. THIS IS THE LAVA THE OBSIDIAN NEEDS and you carry the water_bucket. The lava is about 4 blocks off on bearing 0: the pool's near cell is about (-2991, 10, -5557) (if the pool lies lower than that, the lava is the cell under it), the RIM block to pour from is about (-2991, 10, -5558). Both come from one frame's geometry.
{SEP}
Action 80 | Step 5237 | Plan Step 1/1 | 13/24 verified

[ACTION] fill_bucket(ticks=260) -> 60 ticks
[STATE] pos=(-2991.00, 11.00, -5565.00) pitch=35 yaw=0 moved=0.50
[NOTE] fill_bucket: the bucket filled -- water_bucket +1 (aim 2 of 25, pitch 35 yaw -148, 10 ticks). You now carry 1 water_bucket.
{SEP}
Action 90 | Step 5696 | Plan Step 1/1 | 13/24 verified

[ACTION] {{"forward":1}} x20
[STATE] pos=(-3010.00, 71.00, -5572.00) pitch=0 yaw=0 moved=0.00
[NOTE] YOU DIED at (-2990, 11, -5560) and respawned at (-3010, 71, -5572). Everything you carried dropped at the death point.
"""


def make_life(root: Path, name: str = "life", log: str = LOG) -> Path:
    d = root / name
    (d / "episodes" / "ep_000001" / "observation").mkdir(parents=True)
    (d / "episodes" / "ep_000001" / "observation" / "image.png").write_bytes(b"png")
    (d / "logs.txt").write_text(log, encoding="utf-8")
    (d / "index.jsonl").write_text(json.dumps({
        "id": "ep_000001", "kind": "episode", "first_step": 1, "last_step": 5,
        "tags": [], "summary": "walk", "image": "episodes/ep_000001/observation/image.png",
        "path": "episodes/ep_000001", "action_kind": "forward", "x": 1.0, "y": 64.0,
        "z": 1.0}) + "\n", encoding="utf-8")
    (d / "AGENTS.md").write_text("not carried", encoding="utf-8")
    return d


def test_sites_from_log_reads_what_the_run_verified():
    from mcu_worldmodel.previous import merge_sites, sites_from_log

    sites = merge_sites(sites_from_log(LOG, life=1))
    kinds = {s.kind: s for s in sites}
    assert set(kinds) == {"water", "ore", "lava", "death"}
    assert (kinds["water"].x, kinds["water"].y, kinds["water"].z) == (-3013, 70, -5580)
    # The bucket filled at y 11 beside the lava was the run's own pour, not a source.
    assert all(not (s.kind == "water" and s.y == 11) for s in sites)
    assert kinds["ore"].item == "iron_ore" and kinds["ore"].y == 54.0
    assert kinds["lava"].pool == (-2991, 10, -5557) and kinds["lava"].rim == (-2991, 10, -5558)
    assert "yaw 0" in kinds["lava"].detail          # 720 normalised
    assert kinds["death"].x == -2990


def test_block_orders_by_what_the_chain_needs(tmp_path: Path):
    from mcu_worldmodel.previous import PreviousLives

    life = make_life(tmp_path, "parent")
    pl = PreviousLives(tmp_path / "ws")
    pl.seed([life])
    pos = {"x": -3009.5, "y": 71.0, "z": -5572.5, "pitch": 0.0, "yaw": 0.0}
    unmet = {"mine_obsidian", "flint_and_steel"}
    dry = pl.block(pos, {"bucket": 1}, unmet).splitlines()
    wet = pl.block(pos, {"water_bucket": 1}, unmet).splitlines()
    assert dry[0].startswith("[KNOWN SITES] from 1 previous life")
    assert dry[1].startswith("- STILL WATER") and "8 blocks from you" in dry[1]
    assert wet[1].startswith("- LAVA LAKE") and "make_obsidian(-2991, 10, -5558)" in wet[1]
    assert dry[-1].startswith("- DEATH") and wet[-1].startswith("- DEATH")
    # Obsidian banked: the lava drops behind the ore.
    done = pl.block(pos, {"water_bucket": 1}, {"kill_blaze"}).splitlines()
    assert done[1].startswith("- ORE")
    assert pl.block(None, {}, set()) != ""
    # A 3% sighting is a sliver, ranked after lakes; a pour rim with no lake beside it
    # says so (ob1/ob1b tunnelled to one and poured on stone).
    sliver_log = LOG.replace("33% of the lower view", "3% of the lower view") + f"""{SEP}
Action 95 | Step 6000 | Plan Step 1/1 | 13/24 verified

[ACTION] make_obsidian(x=-2991,y=10,z=-5558) -> 270 ticks
[STATE] pos=(-2991.40, 11.00, -5561.20) pitch=8 yaw=0 moved=0.00
[NOTE] make_obsidian: done at the rim (-2991, 10, -5558) -- every lava SOURCE the water touched is obsidian now.
"""
    make_life(tmp_path, "sliver", sliver_log)
    pl2 = PreviousLives(tmp_path / "ws2")
    pl2.seed([tmp_path / "sliver"])
    wet2 = pl2.block(pos, {"water_bucket": 1}, unmet).splitlines()
    assert wet2[1].startswith("- LAVA SLIVER (not a lake: 3%")
    assert any(l.startswith("- POUR RIM, UNVERIFIED") for l in wet2)
    lake = pl.block(pos, {"water_bucket": 1}, unmet).splitlines()
    assert lake[1].startswith("- LAVA LAKE")
    assert pl.audit()["kinds"] == {"death": 1, "lava": 1, "ore": 1, "water": 1}


def test_seed_links_the_record_and_chains_lives(tmp_path: Path):
    from mcu_worldmodel.previous import PreviousLives, lives_of

    gen1 = make_life(tmp_path, "gen1")
    ws2 = tmp_path / "gen2"
    pl2 = PreviousLives(ws2)
    pl2.seed([gen1])
    assert (ws2 / "previous" / "life_1" / "logs.txt").read_text() == LOG
    assert (ws2 / "previous" / "life_1" / "episodes" / "ep_000001" / "observation"
            / "image.png").exists()
    assert not (ws2 / "previous" / "life_1" / "AGENTS.md").exists()
    rows = [json.loads(l) for l in (ws2 / "previous" / "index.jsonl").read_text().splitlines()]
    assert rows[0]["path"] == "previous/life_1/episodes/ep_000001" and rows[0]["life"] == 1
    assert json.loads((ws2 / "previous" / "sites.json").read_text())["lives"] == [str(gen1)]
    # gen2 becomes a seed itself: its carried life comes first, then its own record.
    (ws2 / "logs.txt").write_text(LOG.replace("-3013, 70, -5580", "-2993, 69, -5572"))
    assert [p.name for p in lives_of(ws2)] == ["life_1", "gen2"]
    pl3 = PreviousLives(tmp_path / "gen3")
    pl3.seed([ws2])
    assert [p.name for p in pl3.lives] == ["life_1", "life_2"]
    assert sum(1 for s in pl3.sites if s.kind == "water") == 2


def test_mfm_sweep_keeps_previous(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory

    mem = MultimodalMemory(tmp_path / "memory", structured=False, episodes=True)
    (mem.root / "previous").mkdir()
    (mem.root / "previous" / "x").write_text("kept")
    (mem.root / "scratch.md").write_text("swept")
    removed = mem.sweep_foreign()
    assert "scratch.md" in removed and (mem.root / "previous" / "x").exists()


def test_chassis_mfm_with_previous_lives(tmp_path: Path):
    """The arm announces the carried lives in AGENTS.md and pushes the sites every
    turn; the store rows the run writes itself are unchanged."""
    from test_pins_chassis import drive_chassis

    life = make_life(tmp_path, "parent")
    agent, actions = drive_chassis(tmp_path, "mfm", previous_lives=[life])
    ws = agent.memory.root
    assert "`previous/life_<i>/`" in (ws / "AGENTS.md").read_text()
    assert (ws / "previous" / "life_1" / "logs.txt").exists()
    turns = [p for p in agent.codex.prompts if "Your memory is" in p]   # not the retry nudges
    assert turns and all("[KNOWN SITES] from 1 previous life" in p for p in turns)
    rep = agent.report()
    assert rep["mfm"]["previous"]["lives"] == 1 and rep["mfm"]["previous"]["pushes"] >= 1
    # The sweep at the end of a turn left the carried record in place.
    assert (ws / "previous" / "index.jsonl").exists()
