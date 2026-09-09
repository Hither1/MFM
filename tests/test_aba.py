"""The A-B-A memory probes: the ledger's ordering gate, and what the prompt discloses.

The tasks are ported from MrSteve (ICLR 2025). Their whole content is that the first and
third goals are the *same* statistic, so two things have to hold or the task is not a
task: a goal must bank nothing before its turn comes (otherwise one trip to the pond
scores both, and the return journey the task exists to measure never happens), and the
agent must not be told at step 0 that the return journey is coming (otherwise it
memorises the pond deliberately, which is the opposite of the incidental encoding the
probe is for).

Both are easy to break by accident from a long way away -- a prompt change, a new wire
field -- so they are pinned here rather than left to the task configs to imply.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "MCU" / "MCU_benchmark" / "task_configs" / "tasks"

ABA = ["aba_water_log_water", "aba_log_water_log",
       "aba_beef_log_beef", "aba_log_beef_log",
       "aba_wool_log_wool", "aba_log_wool_log"]


@pytest.fixture
def ledger_mod():
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info
    return MilestoneLedger, fake_info


# -- the ordering gate ----------------------------------------------------------------

def _aba_cfg():
    """water -> log -> water, the shape every ported task has."""
    return [
        {"event": "use_item", "identity": "water_1", "objects": ["bucket"],
         "reward": 1.0, "max_reward_times": 1},
        {"event": "mine_block", "identity": "log_1", "objects": ["log"],
         "after": ["water_1"], "reward": 1.0, "max_reward_times": 1},
        {"event": "use_item", "identity": "water_2", "objects": ["bucket"],
         "after": ["log_1"], "reward": 1.0, "max_reward_times": 1},
    ]


def test_gate_blocks_out_of_order(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())

    # A log mined before the first bucket is filled banks nothing: log_1 is gated.
    led.update(fake_info(mine_block={"log": 4}), 10)
    assert led.achieved == {}

    # The first fill opens log_1. Note the log statistic is already at 4 and stays there.
    led.update(fake_info(mine_block={"log": 4}, use_item={"bucket": 1}), 20)
    assert set(led.achieved) == {"water_1"}


def test_gate_does_not_credit_the_backlog(ledger_mod):
    """The point of gating on deltas rather than absolute counts.

    An agent that chopped nine logs while the goal was water must still chop one more
    once the log goal opens -- the nine it slept through are not a down payment.
    """
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())
    led.update(fake_info(mine_block={"log": 9}), 10)
    led.update(fake_info(mine_block={"log": 9}, use_item={"bucket": 1}), 20)
    assert set(led.achieved) == {"water_1"}

    # The gate is open and the statistic is high, but it has not *moved*.
    led.update(fake_info(mine_block={"log": 9}, use_item={"bucket": 1}), 21)
    assert set(led.achieved) == {"water_1"}

    led.update(fake_info(mine_block={"log": 10}, use_item={"bucket": 1}), 30)
    assert set(led.achieved) == {"water_1", "log_1"}


def test_one_trip_cannot_score_both_water_goals(ledger_mod):
    """The failure the gate exists to prevent, stated directly."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())
    # Stand at the pond and fill the bucket twice over, never leaving.
    led.update(fake_info(use_item={"bucket": 1}), 10)
    led.update(fake_info(use_item={"bucket": 2}), 11)
    led.update(fake_info(use_item={"bucket": 3}), 12)
    assert set(led.achieved) == {"water_1"}, "the return trip was skipped"
    assert not led.all_done()


def test_full_sequence_scores_three(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())
    led.update(fake_info(use_item={"bucket": 1}), 10)
    led.update(fake_info(use_item={"bucket": 1}, mine_block={"log": 1}), 20)
    led.update(fake_info(use_item={"bucket": 2}, mine_block={"log": 1}), 30)
    assert led.achieved == {"water_1": 10, "log_1": 20, "water_2": 30}
    assert led.all_done()


def test_next_target_never_names_a_gated_goal(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())
    assert led.next_target()["identity"] == "water_1"
    led.update(fake_info(use_item={"bucket": 1}), 10)
    assert led.next_target()["identity"] == "log_1"


# -- what the prompt discloses --------------------------------------------------------

def test_sequential_reveal_hides_the_return_trip(ledger_mod):
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())

    block = led.progress_block()
    assert "water_1" in block
    # Not the identity, not the event, not the objects: `water_2` announces the return
    # trip on its own, which is the one thing the agent must not know yet.
    assert "water_2" not in block and "log_1" not in block
    assert "2 further goal(s)" in block

    led.update(fake_info(use_item={"bucket": 1}), 10)
    block = led.progress_block()
    assert "log_1" in block and "water_2" not in block
    assert "1 further goal(s)" in block


def test_ordered_task_does_not_claim_any_order(ledger_mod):
    """`progress_line` normally tells the agent order does not matter. On these tasks it
    is the only thing that does."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())
    line = led.progress_line()
    assert "ANY order" not in line
    assert "ORDERED" in line and "current goal" in line


def test_wire_spec_is_filtered_to_revealed(ledger_mod):
    """The PRO-LONG arms learn their goals from this payload rather than from
    `progress_block`. Unfiltered, that one arm would see the whole sequence at step 0
    while the others saw one goal -- two arms running two different tasks."""
    MilestoneLedger, fake_info = ledger_mod
    from task_milestones import synthesize_milestone_info
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    led.reset(fake_info())

    payload = synthesize_milestone_info(led.cfg, led.achieved, led.revealed())
    assert [r["identity"] for r in payload["milestone_spec"]] == ["water_1"]
    assert set(payload["milestones"]) == {"water_1"}

    led.update(fake_info(use_item={"bucket": 1}), 10)
    payload = synthesize_milestone_info(led.cfg, led.achieved, led.revealed())
    assert [r["identity"] for r in payload["milestone_spec"]] == ["water_1", "log_1"]


# -- the pre-existing tasks are untouched ---------------------------------------------

def test_ungated_tasks_are_unchanged(ledger_mod):
    """Every task that predates this keeps the exact ledger it had: no gates, full
    disclosure, and the order-free wording the tech-tree runs were measured with."""
    MilestoneLedger, fake_info = ledger_mod
    from task_milestones import load_milestone_cfg, load_reveal_mode

    cfg = load_milestone_cfg("mine_diamond_from_scratch")
    assert load_reveal_mode("mine_diamond_from_scratch") == "all"
    led = MilestoneLedger(cfg, "diamond")
    assert led.reveal == "all"
    assert not led.ordered and not any(led.gate.values())

    led.reset(fake_info())
    block = led.progress_block()
    assert all(c["identity"] in block for c in cfg)
    assert "further goal(s)" not in block
    assert "ANY order" in led.progress_line()

    # And an unfiltered wire payload still carries every rule.
    from task_milestones import synthesize_milestone_info
    assert len(synthesize_milestone_info(cfg, {})["milestone_spec"]) == len(cfg)

    # The report keeps the exact key set the measured runs produced: `gates`/`reveal`
    # appear only where they say something. `tests/pins/chassis_*_report_keys.json` is
    # the same guarantee from the other side.
    assert "gates" not in led.summary() and "reveal" not in led.summary()


def test_aba_report_records_the_gates(ledger_mod):
    """On a gated task the report must say so -- the score is not readable without it."""
    MilestoneLedger, fake_info = ledger_mod
    led = MilestoneLedger(_aba_cfg(), "aba", reveal="sequential")
    assert led.summary()["reveal"] == "sequential"
    assert led.summary()["gates"] == {"log_1": ["water_1"], "water_2": ["log_1"]}


# -- the six task configs -------------------------------------------------------------

@pytest.mark.parametrize("name", ABA)
def test_task_config_is_a_well_formed_aba(name):
    data = yaml.safe_load((TASKS / name / f"{name}.yaml").read_text())
    cfg = data["milestone_reward_cfg"]

    assert data["milestone_reveal"] == "sequential"
    assert len(cfg) == 3, "A-B-A is three goals"

    a1, b, a2 = cfg
    assert a1["event"] == a2["event"] and a1["objects"] == a2["objects"], \
        "the first and third goals must be the same statistic -- that is the task"
    assert b["event"] != a1["event"], "the middle leg must be a different resource"

    # Each goal after the first is gated on exactly the one before it.
    assert "after" not in a1
    assert b["after"] == [a1["identity"]]
    assert a2["after"] == [b["identity"]]

    # The instruction must not leak the sequence.
    text = data["text"].lower()
    for word in ("water", "log", "wood", "bucket", "cow", "beef", "sheep", "wool",
                 "again", "return", "back"):
        assert word not in text, f"task text leaks the sequence: {word!r}"


def _agent_class_sets() -> dict[str, set[str]]:
    """`valid_categories` and `LONG_TASKS` read out of src/agent.py with `ast`.

    Read rather than imported: that module pulls in the a2a server stack, which is not
    installed wherever these offline tests run, and importing a server to check two
    literals would make the check the first thing to be deleted."""
    import ast
    tree = ast.parse((ROOT / "MCU" / "src" / "agent.py").read_text())
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        if node.target.id in ("valid_categories", "LONG_TASKS") and node.value is not None:
            out[node.target.id] = set(ast.literal_eval(node.value))
    return out


@pytest.mark.parametrize("name", ABA)
def test_task_is_registered(name):
    """A category missing from `valid_categories` is rejected at submission; one missing
    from `LONG_TASKS` has its 12,000 steps silently clamped to 1,200 (src/agent.py, the
    `max_steps > DEFAULT_MAX_STEPS` branch), which ends every episode partway through the
    first goal without saying so."""
    sets = _agent_class_sets()
    assert name in sets["valid_categories"]
    assert name in sets["LONG_TASKS"]


def test_inverted_variants_put_the_scarce_leg_in_the_middle():
    """The reason the inverted three exist. MrSteve's own three all put `log` on the
    middle leg, and in a plains world a log is a couple of hundred steps of re-exploring
    -- so the incidental leg is the one leg no arm needs memory for."""
    for name in ["aba_log_water_log", "aba_log_beef_log", "aba_log_wool_log"]:
        cfg = yaml.safe_load((TASKS / name / f"{name}.yaml").read_text())["milestone_reward_cfg"]
        assert cfg[0]["event"] == "mine_block", f"{name}: outer legs should be the log"
        assert cfg[1]["event"] != "mine_block", f"{name}: middle leg should be scarce"
    for name in ["aba_water_log_water", "aba_beef_log_beef", "aba_wool_log_wool"]:
        cfg = yaml.safe_load((TASKS / name / f"{name}.yaml").read_text())["milestone_reward_cfg"]
        assert cfg[1]["event"] == "mine_block", f"{name}: faithful port keeps log middle"


# -- the per-leg scoring script -------------------------------------------------------

def _write_episode(root: Path, i: int, achieved: dict, fname: str) -> None:
    d = root / f"episode_{i:03d}"
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_text(json.dumps({
        "steps": 12000,
        "milestones": {"task": "aba_log_water_log",
                       "order": ["log_1", "water_1", "log_2"],
                       "achieved": achieved, "given": [],
                       "milestones_achieved": len(achieved), "total_milestones": 3},
    }), encoding="utf-8")


@pytest.fixture
def aba_stats():
    sys.path.insert(0, str(ROOT / "MCU" / "scripts"))
    import aba_stats
    return aba_stats


def test_stats_reads_both_arms_report_shapes(aba_stats, tmp_path):
    """The worldmodel arms write worldmodel_report.json and the PRO-LONG arms write
    prolong_milestones.json. A comparison that silently skipped one shape would report
    three arms out of four and look complete."""
    _write_episode(tmp_path / "wm", 0, {"log_1": 10, "water_1": 20, "log_2": 30},
                   "worldmodel_report.json")
    _write_episode(tmp_path / "pl", 0, {"log_1": 10}, "prolong_milestones.json")
    assert len(aba_stats.load_episodes(tmp_path / "wm")) == 1
    assert len(aba_stats.load_episodes(tmp_path / "pl")) == 1


def test_stats_conditionals_are_per_leg(aba_stats, tmp_path):
    """The number the campaign turns on: the incidental leg scored against the episodes
    that actually got far enough to attempt it, not against every episode."""
    root = tmp_path / "arm"
    _write_episode(root, 0, {"log_1": 100, "water_1": 4000, "log_2": 6000}, "worldmodel_report.json")
    _write_episode(root, 1, {"log_1": 100, "water_1": 4000}, "worldmodel_report.json")
    _write_episode(root, 2, {"log_1": 100}, "worldmodel_report.json")
    _write_episode(root, 3, {}, "worldmodel_report.json")

    s = aba_stats.stats(aba_stats.load_episodes(root))
    assert s["n"] == 4
    assert s["reached"] == [3, 2, 1]
    assert s["complete"] == 1
    # incidental leg: 2 of the 3 that reached goal 1. Not 2 of 4.
    assert s["conditional"] == [(2, 3), (1, 2)]
    assert s["median_gap"][1] == 3900


def test_stats_refuses_to_pool_different_tasks(aba_stats, tmp_path, capsys):
    """Two different A-B-A tasks in one directory are not one experiment."""
    root = tmp_path / "mixed"
    _write_episode(root, 0, {"log_1": 10}, "worldmodel_report.json")
    d = root / "episode_001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "worldmodel_report.json").write_text(json.dumps({
        "milestones": {"order": ["water_1", "log_1", "water_2"], "achieved": {}}}))

    assert aba_stats.main([str(root)]) == 1
    assert "not comparable" in capsys.readouterr().err


def test_stats_survives_a_partial_run(aba_stats, tmp_path):
    """A killed episode leaves a truncated report; it must not take the campaign down."""
    root = tmp_path / "arm"
    _write_episode(root, 0, {"log_1": 10, "water_1": 20}, "worldmodel_report.json")
    d = root / "episode_001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "worldmodel_report.json").write_text("{ truncated")
    assert len(aba_stats.load_episodes(root)) == 1
