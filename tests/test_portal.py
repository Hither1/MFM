"""The nether-portal case study: geometry, the privileged channel, and its silence.

The task cuts the dragon chain's one purely geometric goal out of the chain and hands
the agent the obsidian. What makes it a probe rather than a shorter chain is that the
only honest verdict comes from a channel the agent cannot see -- the engine's voxel
query -- and three things about that arrangement break silently if they are wrong:

    the coordinates       `EnvServer` reports voxel hits as OFFSETS from the player's
                          block position with air omitted and the upper bounds
                          exclusive. Read as absolutes, every frame scores 0/10 while
                          the run looks healthy.
    the leak              `voxels` must not reach the agent. An environment that can
                          say "your left column is one short" has answered the
                          question the task asks.
    the false milestone   `use_item: flint_and_steel` fires on a strike into a broken
                          frame. A config that credited it would tell an agent its
                          portal was fine, which is the failure being measured.

Everything here runs without the engine.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "MCU" / "MCU_benchmark" / "task_configs" / "tasks"
CFG = TASKS / "nether_portal" / "nether_portal.yaml"


@pytest.fixture
def P():
    from mcu_worldmodel import portal
    return portal


# -- the shape ------------------------------------------------------------

def test_frame_cells_is_a_portal(P):
    """4 wide, 5 tall, corners excluded from the ten that matter, interior 2x3."""
    for axis in ("x", "z"):
        cells = P.frame_cells((0, 0, 0), axis)
        assert len(cells.required) == 10
        assert len(cells.corners) == 4
        assert len(cells.interior) == 6
        every = set(cells.required) | set(cells.corners) | set(cells.interior)
        assert len(every) == 20, "the 4x5 rectangle is 20 cells and none may repeat"
        xs = {c[0] for c in every}
        ys = {c[1] for c in every}
        zs = {c[2] for c in every}
        assert sorted(ys) == [-1, 0, 1, 2, 3], "five rows"
        free = xs if axis == "x" else zs
        fixed = zs if axis == "x" else xs
        assert len(free) == 4, "four columns"
        assert len(fixed) == 1, "a portal is vertical and planar"


def test_corners_are_not_required(P):
    """Ten obsidian is exactly enough, which is why the task gives exactly ten."""
    cells = P.frame_cells((10, 64, -3), "z")
    assert not (set(cells.corners) & set(cells.required))


# -- reading the engine's answer -------------------------------------------

def _hits(cells, block="minecraft:obsidian", origin=(0, 0, 0)):
    return [{"x": c[0] - origin[0], "y": c[1] - origin[1], "z": c[2] - origin[2],
             "type": block} for c in cells]


def test_parse_voxels_offsets_are_relative_to_the_player(P):
    origin = (100, 64, -50)
    raw = [{"x": 1, "y": 0, "z": -2, "type": "minecraft:obsidian"}]
    assert P.parse_voxels(raw, origin) == {(101, 64, -52): "minecraft:obsidian"}


def test_parse_voxels_accepts_a_json_string(P):
    raw = json.dumps([{"x": 0, "y": 0, "z": 0, "type": "minecraft:stone"}])
    assert P.parse_voxels(raw, (0, 0, 0)) == {(0, 0, 0): "minecraft:stone"}


def test_parse_voxels_refuses_an_unknown_shape(P):
    """None, not {}: an empty dict is a legal answer and would score every frame 0/10."""
    assert P.parse_voxels({"block_name": [[[1]]]}, (0, 0, 0)) is None
    assert P.parse_voxels([{"nope": 1}], (0, 0, 0)) is None
    assert P.parse_voxels("not json", (0, 0, 0)) is None
    assert P.parse_voxels([], (0, 0, 0)) == {}


def test_world_distinguishes_air_from_unseen(P):
    world = P.World()
    world.apply((0, 0, 0), (0, 2, 0, 1, 0, 1), {(0, 0, 0): "minecraft:stone"})
    assert world.state((0, 0, 0)) == "solid"
    assert world.state((1, 0, 0)) == "passable", "covered by the window and empty"
    assert world.state((5, 0, 0)) == "unknown", "never queried"


def test_world_reports_placements_and_minings(P):
    world = P.World()
    win = (0, 2, 0, 1, 0, 1)
    appeared, vanished = world.apply((0, 0, 0), win, {(0, 0, 0): P.OBSIDIAN})
    assert appeared == [((0, 0, 0), P.OBSIDIAN)] and vanished == []
    appeared, vanished = world.apply((0, 0, 0), win, {})
    assert appeared == [] and vanished == [((0, 0, 0), P.OBSIDIAN)]


# -- scoring a build --------------------------------------------------------

def _world_with(P, cells, extra=None, window=(-6, 7, -6, 7, -6, 7), origin=(0, 0, 0)):
    world = P.World()
    blocks = {c: P.OBSIDIAN for c in cells}
    blocks.update(extra or {})
    world.apply(origin, window, blocks)
    return world


def test_a_correct_frame_is_complete(P):
    cells = P.frame_cells((0, 0, 0), "x")
    world = _world_with(P, cells.required)
    best = P.best_fit(world)
    assert best.n_matched == 10 and best.complete and not best.lit
    assert best.anchor == (0, 0, 0)


def test_one_cell_short_is_not_complete(P):
    cells = P.frame_cells((0, 0, 0), "x")
    world = _world_with(P, cells.required[:-1])
    best = P.best_fit(world)
    assert best.n_matched == 9 and not best.complete
    assert list(best.missing) == [cells.required[-1]]


def test_a_block_in_the_interior_blocks_the_portal(P):
    """Ten placed, ten consumed, and the flint and steel still lights a fire."""
    cells = P.frame_cells((0, 0, 0), "x")
    world = _world_with(P, cells.required, extra={cells.interior[0]: P.OBSIDIAN})
    best = P.best_fit(world)
    assert best.n_matched == 10
    assert list(best.blocked) == [cells.interior[0]]
    assert not best.complete


def test_an_unqueried_cell_is_never_scored_complete(P):
    """A frame half outside the window is unknown, not finished."""
    cells = P.frame_cells((0, 0, 0), "x")
    world = P.World()
    world.apply((0, 0, 0), (-6, 7, -6, 2, -6, 7),
                {c: P.OBSIDIAN for c in cells.required if c[1] < 2})
    best = P.best_fit(world)
    assert best.unknown and not best.complete


def test_stray_obsidian_is_the_wasted_block(P):
    cells = P.frame_cells((0, 0, 0), "x")
    stray = (4, 0, 4)
    world = _world_with(P, list(cells.required[:9]) + [stray])
    best = P.best_fit(world)
    assert best.n_matched == 9
    assert P.stray_obsidian(world, best) == [stray]


def test_a_lit_portal_is_read_from_the_portal_blocks(P):
    cells = P.frame_cells((0, 0, 0), "z")
    world = _world_with(P, cells.required,
                        extra={c: P.PORTAL for c in cells.interior})
    best = P.best_fit(world)
    assert best.complete and best.lit and best.lit_cells == 6


def test_dimension_jump_is_the_coordinate_scale(P):
    """`biome_id` reads 0 in both dimensions here, so the x/8 shrink is the signal."""
    assert P.dimension_jump((800.0, -400.0), (100.0, -50.0))
    assert not P.dimension_jump((800.0, -400.0), (805.0, -402.0))


# -- the trace over a whole build -------------------------------------------

def test_trace_records_a_wrong_strike_then_a_right_one(P):
    """The shape the wave showed: a strike into a wrong frame, a fix, a portal."""
    cells = P.frame_cells((0, 0, 0), "x")
    win = (-6, 7, -6, 7, -6, 7)
    trace = P.PortalTrace(window=win)
    good, wrong = list(cells.required[:9]), (4, 0, 4)

    trace.observe(100, (0, 0, 0), _hits(good + [wrong]))
    ig = trace.note_ignition(110)
    assert ig.fit["matched"] == 9 and not ig.lit
    assert ig.stray == [list(wrong)]

    # mined back and re-placed in the cell it belonged in
    trace.observe(200, (0, 0, 0), _hits(good))
    trace.observe(300, (0, 0, 0), _hits(list(cells.required)))
    assert trace.first_complete_step == 300

    lit = _hits(list(cells.required)) + _hits(cells.interior, P.PORTAL)
    trace.observe(400, (0, 0, 0), lit)
    trace.note_ignition(400)
    assert trace.first_lit_step == 400

    s = trace.summary()
    assert s["counts"]["obsidian_placed"] == 11, "ten cells plus the one re-placed"
    assert s["counts"]["obsidian_mined"] == 1
    assert s["counts"]["obsidian_placed_into_unused_cells"] == 1
    assert s["counts"]["ignitions"] == 2
    assert s["first_ignition_matched"] == 9
    assert s["best_frame"]["complete"] and s["best_frame"]["lit"]


def test_trace_counts_an_unreadable_channel_instead_of_scoring_zero(P):
    trace = P.PortalTrace()
    assert trace.observe(1, (0, 0, 0), {"block_name": []}) is False
    assert trace.unreadable == 1 and trace.samples == 0


def test_the_report_carries_no_health_column(P):
    """The task is the shape. Fire damage is a side effect and measures nothing here."""
    keys = P.PortalTrace().summary()
    assert "health" not in keys
    assert not hasattr(P.PortalTrace(), "note_health")


# -- the callback -----------------------------------------------------------

@pytest.fixture
def probe(tmp_path):
    from mcu_worldmodel.portal_probe import PortalProbeCallback
    return PortalProbeCallback(output_dir=tmp_path, window=[-6, 7, -6, 7, -6, 7],
                               every=10, snapshots=False)


def _info(x=0.5, y=0.0, z=0.5, **stats):
    from mcu_worldmodel.testing import fake_info
    info = fake_info(**stats)
    info["location_stats"]["xpos"] = x
    info["location_stats"]["ypos"] = y
    info["location_stats"]["zpos"] = z
    return info


def test_probe_asks_for_voxels_on_a_cadence(probe):
    assert probe.before_step(None, {})["voxels"] == [-6, 7, -6, 7, -6, 7]
    probe.step = 5
    assert "voxels" not in probe.before_step(None, {})
    probe.step = 10
    assert "voxels" in probe.before_step(None, {})


def test_probe_never_writes_into_info(probe, P):
    probe.after_reset(None, {}, _info())
    info = _info()
    info["voxels"] = _hits(P.frame_cells((0, 0, 0), "x").required)
    before = set(info)
    probe.before_step(None, {})
    _obs, _r, _t, _tr, out = probe.after_step(None, {}, 0.0, False, False, info)
    assert set(out) == before, "the probe reads the privileged channel and adds nothing"
    assert probe.trace.samples == 1


def _step(probe, info):
    probe.before_step(None, {})
    return probe.after_step(None, {}, 0.0, False, False, info)


def test_probe_scores_a_strike_from_the_look_that_follows_it(probe, P):
    """Not from the last cadence sample.

    The agent that places its tenth block and strikes four steps later must not be
    recorded as having struck at 9/10 -- that number is the whole measurement. A strike
    forces the next query and is scored from it.
    """
    probe.after_reset(None, {}, _info())
    cells = P.frame_cells((0, 0, 0), "x")

    nine = _info(use_item={"flint_and_steel": 0})
    nine["voxels"] = _hits(cells.required[:9])
    _step(probe, nine)                                     # step 1, on the cadence

    placed = _info(use_item={"flint_and_steel": 0})        # tenth block goes down, and
    _step(probe, placed)                                   # step 2 is not a sample step
    assert probe.trace.samples == 1

    struck = _info(use_item={"flint_and_steel": 1})
    _step(probe, struck)                                   # step 3: the strike
    assert not probe.trace.ignitions, "held until the frame has been looked at"
    assert probe._force, "and the next step is forced to look"

    after = _info(use_item={"flint_and_steel": 1})
    after["voxels"] = _hits(list(cells.required))
    _step(probe, after)                                    # step 4: the forced look
    assert len(probe.trace.ignitions) == 1
    assert probe.trace.ignitions[0].step == 3
    assert probe.trace.ignitions[0].fit["matched"] == 10


def test_probe_scores_the_frame_at_each_strike(probe, P, tmp_path):
    probe.after_reset(None, {}, _info())
    cells = P.frame_cells((0, 0, 0), "x")

    info = _info(use_item={"flint_and_steel": 0})
    info["voxels"] = _hits(cells.required[:9])
    _step(probe, info)

    struck = _info(use_item={"flint_and_steel": 1})
    _step(probe, struck)
    follow = _info(use_item={"flint_and_steel": 1})
    follow["voxels"] = _hits(cells.required[:9])
    _step(probe, follow)

    assert len(probe.trace.ignitions) == 1
    assert probe.trace.ignitions[0].fit["matched"] == 9
    assert probe.trace.ignitions[0].lit is False

    path = probe.write()
    report = json.loads(Path(path).read_text())
    assert report["counts"]["ignitions"] == 1
    assert report["first_ignition_matched"] == 9
    assert report["steps"] == 3


def test_a_strike_on_the_last_step_is_still_scored(probe, P):
    probe.after_reset(None, {}, _info())
    cells = P.frame_cells((0, 0, 0), "x")
    info = _info(use_item={"flint_and_steel": 0})
    info["voxels"] = _hits(cells.required[:8])
    _step(probe, info)
    _step(probe, _info(use_item={"flint_and_steel": 1}))
    assert not probe.trace.ignitions
    report = json.loads(Path(probe.write()).read_text())
    assert report["counts"]["ignitions"] == 1
    assert report["first_ignition_matched"] == 8


def test_probe_ignores_a_stale_voxel_answer(probe, P):
    """`MinecraftSim._wrap_obs_info` accumulates info keys and never clears them.

    So `info["voxels"]` survives from the step that asked for it into every later step.
    Folding it in again would place the same block list against a new player position
    and fill the map with blocks that were never there.
    """
    probe.after_reset(None, {}, _info())
    cells = P.frame_cells((0, 0, 0), "x")
    answer = _hits(cells.required)

    probe.before_step(None, {})                       # step 0: asked
    fresh = _info()
    fresh["voxels"] = answer
    probe.after_step(None, {}, 0.0, False, False, fresh)
    assert probe.trace.samples == 1

    probe.before_step(None, {})                       # step 1: not on the cadence
    stale = _info(x=40.5, z=40.5)                     # and the agent has walked away
    stale["voxels"] = answer                          # the engine's answer is still here
    probe.after_step(None, {}, 0.0, False, False, stale)
    assert probe.trace.samples == 1, "a stale answer must not be folded in"
    assert P.best_fit(probe.trace.world).n_matched == 10, "and must not add phantoms"


def test_probe_survives_a_broken_step(probe):
    """A scoring probe must never be able to kill an episode."""
    probe.after_reset(None, {}, _info())
    probe.before_step(None, {})
    broken = _info()
    broken["voxels"] = object()                       # not a list, not a dict, not JSON
    out = probe.after_step(None, {}, 0.0, False, False, broken)
    assert out[0] == {} and out[1] == 0.0             # the step is returned untouched
    assert probe.trace.unreadable == 1 and probe.trace.samples == 0


def test_probe_refuses_a_window_the_engine_would_clip():
    from mcu_worldmodel.portal_probe import PortalProbeCallback
    with pytest.raises(ValueError):
        PortalProbeCallback(output_dir="/tmp", window=[-60, 60, -5, 6, -8, 9])
    with pytest.raises(ValueError):
        PortalProbeCallback(output_dir="/tmp", window=[-8, 9, -5, 6])


# -- the task configs -------------------------------------------------------

def test_nothing_in_the_kit_is_scarce():
    """The task asks for a shape, not for thrift.

    An earlier version handed out exactly ten obsidian, the minimum, so a misplacement
    had to be mined back -- and the first wave measured recovery cost rather than
    geometry. Supply is now removed as a variable: enough obsidian that no agent can be
    stuck, enough cobblestone to stand on, and a pickaxe so any block can be moved.
    """
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    give = [c for c in cfg["custom_init_commands"] if c.startswith("/give")]
    kit = {c.split()[2].split(":")[-1]: int(c.split()[3]) for c in give}
    assert kit["obsidian"] >= 32, "a portal needs 10; scarcity is not what is measured"
    assert kit["cobblestone"] >= 32 and kit["diamond_pickaxe"] == 1
    assert kit["flint_and_steel"] == 1


def test_there_is_no_scarcity_variant_left():
    assert not (TASKS / "nether_portal_slack").exists()


def test_commands_survive_the_engine(path=CFG):
    """Minecraft truncates any command over 256 characters silently."""
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for cmd in cfg["custom_init_commands"]:
        assert len(cmd) < 256, cmd


def test_world_is_pinned_and_the_pad_is_flat(path=CFG):
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert cfg["world_seed"] == 42 and cfg["spawn_biome"] == "plains"
    fills = [c for c in cfg["custom_init_commands"] if c.startswith("/fill")]
    assert len(fills) == 2, "a floor and the air over it"
    assert fills[0].endswith("minecraft:stone") and fills[1].endswith("minecraft:air")


def test_no_milestone_credits_a_failed_strike(path=CFG):
    """`use_item: flint_and_steel` fires on a strike into a broken frame."""
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = cfg["milestone_reward_cfg"]
    for rule in rules:
        assert not (rule["event"] == "use_item"
                    and "flint_and_steel" in rule["objects"])
    idents = [r["identity"] for r in rules]
    assert idents == ["place_obsidian", "enter_nether"]
    assert rules[1]["after"] == ["place_obsidian"], "order, not just presence"


def test_probe_spec_is_loadable(path=CFG):
    from mcu_worldmodel.portal_probe import PortalProbeCallback
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec = cfg["portal_probe"]
    cb = PortalProbeCallback(output_dir="/tmp", **spec)
    x0, x1, y0, y1, z0, z1 = cb.window
    assert y1 - y0 >= 10, "a 5-tall frame seen from a 4-block pillar needs 10 rows"
    assert x1 - x0 >= 12 and z1 - z0 >= 12


def _agent_class_sets() -> dict[str, set[str]]:
    """`INFO_PASSTHROUGH`, `valid_categories` and `LONG_TASKS`, read out of
    src/agent.py with `ast` rather than imported -- that module pulls in the a2a server
    stack, which is not installed wherever these offline tests run."""
    import ast
    tree = ast.parse((ROOT / "MCU" / "src" / "agent.py").read_text(encoding="utf-8"))
    want = ("INFO_PASSTHROUGH", "valid_categories", "LONG_TASKS")
    return {n.target.id: set(ast.literal_eval(n.value))
            for n in ast.walk(tree)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            and n.target.id in want and n.value is not None}


def test_the_privileged_channel_does_not_reach_the_agent():
    """The whole probe rests on this: `voxels` is not forwarded to the purple agent."""
    sets = _agent_class_sets()
    assert "voxels" not in sets["INFO_PASSTHROUGH"]
    assert "nether_portal" in sets["valid_categories"]
    assert "nether_portal" in sets["LONG_TASKS"], "or --max-steps is clamped to 1200"


def test_the_green_runner_installs_the_probe_for_this_task_only():
    """Gated on the config key, like the scheduled-command callback beside it."""
    source = (ROOT / "MCU" / "src" / "agent.py").read_text(encoding="utf-8")
    assert "probe = load_portal_probe(task)" in source
    assert "if probe:" in source, "no config key, no callback, no change anywhere else"


def test_the_nether_side_portal_cannot_be_scored_as_the_agents_work(P):
    """Once the agent steps through, the voxel answers describe the engine's own portal.

    The map is keyed by absolute cell and the Nether's coordinates are the Overworld's
    over eight, so the two do not collide, they accumulate -- and the Nether side of any
    portal is a game-generated, perfectly legal, already-lit frame. Measured on the
    second wave: `arc` and `mfm` came back with `best_frame.anchor` at the
    NETHER portal, which scored all fourteen of their real placements as "into a cell the
    frame does not use" and turned a precise build into an apparent pile of waste.
    """
    trace = P.PortalTrace(window=(-6, 7, -6, 7, -6, 7))
    over = P.frame_cells((0, 0, 0), "x")
    trace.observe(100, (0, 0, 0), _hits(over.required))
    assert P.best_fit(trace.world).anchor == (0, 0, 0)

    trace.dimension_step = 200          # the agent steps through
    nether = P.frame_cells((5000, 0, 5000), "x")
    accepted = trace.observe(300, (5000, 0, 5000),
                             _hits(list(nether.required) + list(nether.corners)))
    assert accepted is False, "a post-transit sample is refused, not folded"
    best = P.best_fit(trace.world)
    assert best.anchor == (0, 0, 0), "the frame scored is the one the agent built"
    assert P.stray_obsidian(trace.world, best) == []
