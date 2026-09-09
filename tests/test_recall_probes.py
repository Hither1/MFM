"""The recall probes: a place-based goal, and a landmark that stops existing.

MrSteve's §4.3 memory tasks turn on three properties, and the ABA machinery only supplied
one of them (encoding with no task active, via `milestone_reveal: sequential`). The other
two are here:

    the target cannot be re-perceived   a scheduled command removes the landmark long
                                        before the goal that asks for it is revealed, so
                                        looking around is not a substitute for having
                                        remembered
    success is a PLACE                  `event: reach`, scored on player position; the
                                        ledger otherwise only knows statistics

Both are easy to get subtly wrong in ways a run would not report -- a landmark removed at
the agent's feet instead of where it was left, a reach rule the green scorer crashes on --
so they are pinned here.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "MCU" / "MCU_benchmark" / "task_configs" / "tasks" / "recall_vanished_fire"


@pytest.fixture
def ledger_mod():
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info
    return MilestoneLedger, fake_info


def _at(fake_info, x: float, z: float, **stats):
    info = fake_info(**stats)
    info["location_stats"]["xpos"] = x
    info["location_stats"]["zpos"] = z
    return info


def _cfg():
    return [
        {"event": "mine_block", "identity": "chop_wood", "objects": ["log"],
         "reward": 1.0, "max_reward_times": 1},
        {"event": "reach", "identity": "return_to_fire", "objects": [],
         "target": [0, 0], "radius": 6, "after": ["chop_wood"],
         "reward": 1.0, "max_reward_times": 1},
    ]


# -- the reach rule --------------------------------------------------------------------

def test_reach_targets_are_relative_to_where_the_episode_began(ledger_mod):
    """A task config cannot name absolute coordinates: the spawn point is whatever the
    seed puts there, and the landmark is placed with `~` offsets from it."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 1000.0, -2000.0))
    assert led.origin == (1000.0, -2000.0)
    assert led.reach_target(led.cfg[1]) == (1000.0, -2000.0)


def test_reach_fires_only_inside_the_radius(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 100.0, 100.0))
    led.update(_at(fake_info, 130.0, 100.0, mine_block={"log": 1}), 10)
    assert set(led.achieved) == {"chop_wood"}

    # 20 blocks out: still away.
    led.update(_at(fake_info, 120.0, 100.0, mine_block={"log": 1}), 20)
    assert set(led.achieved) == {"chop_wood"}

    # 4 blocks out: within the 6-block radius.
    led.update(_at(fake_info, 104.0, 100.0, mine_block={"log": 1}), 30)
    assert led.achieved["return_to_fire"] == 30


def test_reach_respects_its_gate(ledger_mod):
    """Standing on the spot before the goal exists banks nothing -- the agent starts
    there, so without the gate the task would be complete at step 1."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 100.0, 100.0))
    for step in (1, 2, 3):
        led.update(_at(fake_info, 100.0, 100.0), step)
    assert led.achieved == {}

    led.update(_at(fake_info, 300.0, 300.0, mine_block={"log": 1}), 10)
    led.update(_at(fake_info, 100.0, 100.0, mine_block={"log": 1}), 20)
    assert set(led.achieved) == {"chop_wood", "return_to_fire"}


def test_reach_survives_a_missing_position(ledger_mod):
    """`location()` returns None when location_stats is absent; that must not fire the
    rule and must not raise."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    info = fake_info()
    info.pop("location_stats")
    led.reset(info)
    assert led.origin is None
    assert led.reach_target(led.cfg[1]) is None
    led.update(dict(info, mine_block={"log": 1}), 10)
    assert "return_to_fire" not in led.achieved


def test_reach_is_never_waiting_on_a_host_bit(ledger_mod):
    """The green scorer only knows statistics, so `info['milestones']` can never carry a
    bit for a reach rule. If the published branch swallowed it the goal would be
    unachievable for the whole episode."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))
    info = _at(fake_info, 500.0, 0.0, mine_block={"log": 1})
    info["milestones"] = {"chop_wood": 1, "return_to_fire": 0}
    led.update(info, 10)
    back = _at(fake_info, 1.0, 1.0, mine_block={"log": 1})
    back["milestones"] = {"chop_wood": 1, "return_to_fire": 0}
    led.update(back, 20)
    assert led.achieved["return_to_fire"] == 20


def test_reach_renders_in_the_prompt_without_a_statistic(ledger_mod):
    """`progress_block` renders `objects` for every other rule; a reach rule has none and
    would print an empty list. It must also not fall back to coordinates -- see
    test_a_reach_goal_never_prints_its_coordinates."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_cfg(), "recall", reveal="all")
    led.reset(_at(fake_info, 10.0, 20.0))
    block = led.progress_block()
    assert "go back to a place you have already been" in block
    assert "within 6 blocks" in block
    assert "x=" not in block and "[]" not in block

    # after chop_wood the reach rule is the current goal
    led2 = MilestoneLedger(_cfg(), "recall", reveal="sequential")
    led2.reset(_at(fake_info, 10.0, 20.0))
    led2.update(_at(fake_info, 500.0, 500.0, mine_block={"log": 1}), 5)
    assert "return to a place you have already been" in led2.progress_line()


# -- the scheduled landmark removal ----------------------------------------------------

@pytest.fixture
def scheduled():
    from mcu_worldmodel.scheduled import ScheduledCommandsCallback
    return ScheduledCommandsCallback


def test_placeholders_resolve_against_the_episode_start(scheduled):
    """`~` is wrong here and silently so: it resolves against the agent's position when
    the command runs, hundreds of steps after it walked away from the landmark."""
    cb = scheduled([{"step": 600, "commands": ["/fill {x-4} {y} {z-4} {x+4} {y+2} {z+4} minecraft:air"]}])
    cb.origin = (100, 64, -250)
    assert cb.resolve("/fill {x-4} {y} {z-4} {x+4} {y+2} {z+4} minecraft:air") == \
        "/fill 96 64 -254 104 66 -246 minecraft:air"


def test_nbt_braces_are_left_alone(scheduled):
    """Why this is a regex over `{axis±offset}` and not `str.format`."""
    cb = scheduled([])
    cb.origin = (0, 64, 0)
    cmd = '/give @s minecraft:shovel{Enchantments:[{id:"minecraft:efficiency",lvl:1}]} 1'
    assert cb.resolve(cmd) == cmd


def test_unresolvable_origin_leaves_the_command_alone(scheduled):
    cb = scheduled([])
    assert cb.origin is None
    assert cb.resolve("/fill {x-4} {y} {z-4} air") == "/fill {x-4} {y} {z-4} air"


def test_fires_once_at_its_step(scheduled):
    class FakeEnv:
        def __init__(self): self.ran = []
        def execute_cmd(self, c): self.ran.append(c)

    class FakeSim:
        def __init__(self): self.env = FakeEnv()

    cb = scheduled([{"step": 3, "commands": ["/tp @s {x} {y} {z}"]}])
    sim = FakeSim()
    info = {"location_stats": {"xpos": 7.0, "ypos": 64.0, "zpos": -8.0}}
    cb.after_reset(sim, {}, info)
    for _ in range(6):
        cb.after_step(sim, {}, 0.0, False, False, info)
    assert sim.env.ran == ["/tp @s 7 64 -8"], "must fire exactly once, with origin substituted"
    assert cb.fired == [{"step": 3, "commands": ["/tp @s {x} {y} {z}"]}]


def test_a_failing_command_does_not_kill_the_episode(scheduled):
    class BadEnv:
        def execute_cmd(self, c): raise RuntimeError("engine said no")

    class FakeSim:
        env = BadEnv()

    cb = scheduled([{"step": 1, "commands": ["/nope"]}])
    cb.after_reset(FakeSim(), {}, {"location_stats": {"xpos": 0, "ypos": 0, "zpos": 0}})
    out = cb.after_step(FakeSim(), {"o": 1}, 0.0, False, False, {})
    assert out[0] == {"o": 1}


# -- the task config -------------------------------------------------------------------

def test_task_config_is_a_recall_probe():
    data = yaml.safe_load((TASK_DIR / "recall_vanished_fire.yaml").read_text())
    cfg = data["milestone_reward_cfg"]
    assert data["milestone_reveal"] == "sequential"

    errand, recall = cfg
    assert recall["event"] == "reach"
    assert recall["after"] == [errand["identity"]]
    # Required by the green agent's RewardsCallback, which indexes `objects` on every
    # rule; empty so it never scores a rule it cannot evaluate.
    assert recall["objects"] == []

    # The landmark must be gone before the goal that asks for it can be revealed. Asserted
    # as a relation, not a constant: the step scales are calibrated to arm cadence and get
    # re-derived (they moved 600 -> 7,000 on 2026-09-07 when mfm turned out to average ~714
    # steps a turn, so the fire vanished before its first turn ended).
    removal_step = data["scheduled_commands"][0]["step"]
    assert recall["not_before"] > removal_step, \
        f"goal opens at {recall['not_before']} but the landmark is removed at {removal_step}"
    removal = " ".join(data["scheduled_commands"][0]["commands"])
    assert "minecraft:fire" in removal and "grass_block" in removal
    assert "~" not in removal, "scheduled removal must be absolute; ~ follows the agent"


def test_recall_task_is_registered():
    import ast
    tree = ast.parse((ROOT / "MCU" / "src" / "agent.py").read_text())
    sets = {n.target.id: set(ast.literal_eval(n.value))
            for n in ast.walk(tree)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            and n.target.id in ("valid_categories", "LONG_TASKS") and n.value is not None}
    assert "recall_vanished_fire" in sets["valid_categories"]
    assert "recall_vanished_fire" in sets["LONG_TASKS"]


# -- goals gated on time, not on another goal ------------------------------------------

def _timed_cfg(not_before=1000):
    return [{"event": "reach", "identity": "return_to_fire_pit", "objects": [],
             "target": [70, 0], "radius": 10, "not_before": not_before,
             "describe": "the place where you saw a patch of ground burning",
             "reward": 1.0, "max_reward_times": 1}]


def test_not_before_keeps_the_prologue_task_free(ledger_mod):
    """Long-Navigation's exploration phase has NO goal, not a hidden one. `after:` cannot
    express that -- there is no earlier goal to hang it on."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_timed_cfg(1000), "longnav", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))

    # Standing exactly on the target during the prologue banks nothing...
    led.update(_at(fake_info, 70.0, 0.0), 500)
    assert led.achieved == {}
    # ...and the checklist names nothing at all.
    assert "return_to_fire_pit" not in led.progress_block()
    assert "1 further goal(s)" in led.progress_block()

    # After the gate opens it is the current goal, and reaching it counts.
    led.update(_at(fake_info, 0.0, 0.0), 1000)
    assert "return_to_fire_pit" in led.progress_block()
    led.update(_at(fake_info, 70.0, 0.0), 1100)
    assert led.achieved["return_to_fire_pit"] == 1100


def test_not_before_makes_a_task_ordered(ledger_mod):
    """A single time-gated goal is still an ordered task: `progress_line` must not tell
    the agent order is free."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_timed_cfg(), "longnav", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))
    assert led.ordered
    assert "ANY order" not in led.progress_line()
    assert led.summary()["not_before"] == {"return_to_fire_pit": 1000}


def test_ungated_task_reports_no_not_before(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    from task_milestones import load_milestone_cfg
    led = MilestoneLedger(load_milestone_cfg("mine_diamond_from_scratch"), "d")
    assert not led.ordered and "not_before" not in led.summary()


# -- the coordinate leak ---------------------------------------------------------------

def test_a_reach_goal_never_prints_its_coordinates(ledger_mod):
    """The one bug that would silently void every recall probe: naming the target as
    numbers hands the agent the answer at the moment the goal is revealed."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_timed_cfg(0), "longnav", reveal="sequential")
    led.reset(_at(fake_info, 1234.0, -5678.0))
    for text in (led.progress_block(), led.progress_line()):
        assert "1304" not in text and "-5678" not in text and "x=" not in text
    assert "patch of ground burning" in led.progress_block()


def test_reach_falls_back_to_a_non_numeric_phrase(ledger_mod):
    """A rule with no `describe:` still must not leak coordinates."""
    MilestoneLedger, fake_info = ledger_mod
    cfg = _timed_cfg(0)
    cfg[0].pop("describe")
    led = MilestoneLedger(cfg, "t", reveal="sequential")
    led.reset(_at(fake_info, 1234.0, -5678.0))
    assert "a place you have already been" in led.progress_block()
    assert "x=" not in led.progress_block()


def test_reveal_target_is_opt_in(ledger_mod):
    """Escape hatch for a task that genuinely wants to name the spot."""
    MilestoneLedger, fake_info = ledger_mod
    cfg = _timed_cfg(0)
    cfg[0]["reveal_target"] = True
    led = MilestoneLedger(cfg, "t", reveal="sequential")
    led.reset(_at(fake_info, 100.0, 200.0))
    assert "x=170 z=200" in led.progress_block()


# -- the two prologue tasks ------------------------------------------------------------

TASKS = ROOT / "MCU" / "MCU_benchmark" / "task_configs" / "tasks"


@pytest.mark.parametrize("name", ["recall_first_house", "recall_long_navigation"])
def test_prologue_task_is_well_formed(name):
    data = yaml.safe_load((TASKS / name / f"{name}.yaml").read_text())
    goal = data["milestone_reward_cfg"][0]
    assert goal["event"] == "reach" and goal["objects"] == []
    assert data["milestone_reveal"] == "sequential"

    # The goal must not open until the prologue has finished moving the agent about,
    # or the "no task at all" phase is not task-free.
    last_move = max(s["step"] for s in data["scheduled_commands"])
    assert goal["not_before"] > last_move, \
        f"{name}: goal opens at {goal['not_before']} but the prologue runs to {last_move}"

    # Named, never numbered.
    assert goal.get("describe") and not goal.get("reveal_target")

    # Every scheduled command is absolute: `~` follows the agent, and the agent has been
    # teleported away by the time these run.
    for entry in data["scheduled_commands"]:
        for cmd in entry["commands"]:
            assert "~" not in cmd, f"{name}: relative coords in a scheduled command: {cmd}"


def test_first_house_radius_cannot_credit_the_second_house():
    """Both huts are identical, so only the radius stops the wrong one scoring."""
    import math
    data = yaml.safe_load((TASKS / "recall_first_house" / "recall_first_house.yaml").read_text())
    goal = data["milestone_reward_cfg"][0]
    # House B is where the second teleport puts the agent -- found by order, not by a
    # hardcoded step, because the prologue's scale is recalibrated per cadence band.
    tps = [s for s in data["scheduled_commands"]
           if any("/tp" in c for c in s["commands"])]
    second = sorted(tps, key=lambda s: s["step"])[1]["commands"][0]
    assert "{z+50}" in second and "{x}" in second        # (0, +50)
    separation = math.dist(goal["target"], [0, 50])
    assert separation > 2 * goal["radius"], \
        f"houses {separation:.0f} apart but radius is {goal['radius']}"


def test_long_navigation_target_is_removed_before_it_is_asked_for():
    """The point of picking a transient landmark: it cannot be re-perceived."""
    data = yaml.safe_load((TASKS / "recall_long_navigation" /
                           "recall_long_navigation.yaml").read_text())
    goal = data["milestone_reward_cfg"][0]
    removals = [s for s in data["scheduled_commands"]
                if any("replace minecraft:fire" in c for c in s["commands"])]
    assert removals, "the fire pit is never extinguished"
    assert removals[0]["step"] < goal["not_before"]


@pytest.mark.parametrize("name", ["recall_first_house", "recall_long_navigation"])
def test_prologue_task_is_registered(name):
    import ast
    tree = ast.parse((ROOT / "MCU" / "src" / "agent.py").read_text())
    sets = {n.target.id: set(ast.literal_eval(n.value))
            for n in ast.walk(tree)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            and n.target.id in ("valid_categories", "LONG_TASKS") and n.value is not None}
    assert name in sets["valid_categories"] and name in sets["LONG_TASKS"]


# -- a goal that is merely not open yet is not a finished episode ----------------------


def _gated_pair_cfg():
    """`_cfg()` but with the return trip held shut until the landmark is gone."""
    cfg = _cfg()
    cfg[1]["not_before"] = 7200
    return cfg


def test_pending_goal_is_not_reported_as_all_verified(ledger_mod):
    """A goal held shut by `not_before` must not read as the end of the episode.

    The first cut of `progress_line()` said "ALL GOALS VERIFIED" whenever
    `next_target()` was None -- which is also true while a time-gated goal waits,
    so the line claimed "1/2 goals" and "ALL GOALS VERIFIED" in one breath. The
    agent believed the verdict over the count: rvf2_mfm spent 328 act turns idling
    on "All goals are verified; no further progression is needed."
    """
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_gated_pair_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))
    led.update(_at(fake_info, 0.0, 0.0, mine_block={"log": 1}), 269)

    line = led.progress_line()
    assert not led.all_done()
    assert "ALL GOALS VERIFIED" not in line
    assert "NOT over" in line
    assert "1 further goal" in line


def test_pending_wording_does_not_describe_the_hidden_goal(ledger_mod):
    """The probe measures INCIDENTAL encoding, so the waiting line must stay thin.

    Telling the agent a return trip is coming -- or that landmarks are worth
    noting -- converts the thing being measured into instructed encoding.
    """
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_gated_pair_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))
    led.update(_at(fake_info, 0.0, 0.0, mine_block={"log": 1}), 269)

    tail = led.progress_line().split("No goal is live")[-1].lower()
    for leak in ("return", "fire", "remember", "landmark", "back"):
        assert leak not in tail


def test_all_verified_is_still_said_when_the_episode_really_is_over(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_gated_pair_cfg(), "recall", reveal="sequential")
    led.reset(_at(fake_info, 0.0, 0.0))
    led.update(_at(fake_info, 0.0, 0.0, mine_block={"log": 1}), 269)
    led.update(_at(fake_info, 0.0, 0.0), 7300)
    assert led.all_done()
    assert "ALL GOALS VERIFIED" in led.progress_line()
