"""The mfm arm's carried lives (mcu_worldmodel/previous.py): what a seed brings under
previous/, and that the chassis keeps and announces them."""
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
    assert pl2.sources == [str(gen1)]
    # gen2 becomes a seed itself: its carried life comes first, then its own record.
    (ws2 / "logs.txt").write_text(LOG.replace("-3013, 70, -5580", "-2993, 69, -5572"))
    assert [p.name for p in lives_of(ws2)] == ["life_1", "gen2"]
    pl3 = PreviousLives(tmp_path / "gen3")
    pl3.seed([ws2])
    assert [p.name for p in pl3.lives] == ["life_1", "life_2"]


def test_mfm_sweep_keeps_previous(tmp_path: Path):
    from mcu_worldmodel.memory import MultimodalMemory

    mem = MultimodalMemory(tmp_path / "memory", episodes=True)
    (mem.root / "previous").mkdir()
    (mem.root / "previous" / "x").write_text("kept")
    (mem.root / "scratch.md").write_text("swept")
    removed = mem.sweep_foreign()
    assert "scratch.md" in removed and (mem.root / "previous" / "x").exists()


def test_chassis_mfm_carry(tmp_path: Path):
    """The MFM carry: the lives' records -- the log, the episodes,
    the index and whatever the model wrote -- are linked under previous/ and named in
    AGENTS.md; nothing of them is pushed into a turn, and no site digest is written."""
    from test_pins_chassis import drive_chassis

    life = make_life(tmp_path, "parent")
    (life / "locations").mkdir()
    (life / "locations" / "water.md").write_text("pond at (-3013, 70, -5580)", encoding="utf-8")
    (life / "tools").mkdir()
    (life / "tools" / "episodes.py").write_text("machinery", encoding="utf-8")
    agent, actions = drive_chassis(tmp_path, "mfm", previous_lives=[life])
    ws = agent.memory.root
    contract = (ws / "AGENTS.md").read_text()
    assert "`previous/life_<i>/`" in contract and "is yours to do" in contract
    assert "[KNOWN SITES]" not in contract and "DRY CORRIDOR" not in contract
    prev = ws / "previous" / "life_1"
    assert (prev / "logs.txt").exists() and (prev / "index.jsonl").exists()
    assert (prev / "locations" / "water.md").read_text() == "pond at (-3013, 70, -5580)"
    assert not (prev / "AGENTS.md").exists() and not (prev / "tools").exists()
    assert (ws / "previous" / "index.jsonl").exists()
    assert not (ws / "previous" / "sites.json").exists()
    turns = [p for p in agent.codex.prompts if "Your memory is" in p]
    assert turns and not any("[KNOWN SITES]" in p for p in turns)
    rep = agent.report()
    assert rep["mfm"]["previous"]["lives"] == 1

