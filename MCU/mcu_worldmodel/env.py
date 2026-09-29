"""Building the MCU environment for a long-horizon task.

Two things here are not obvious and both will silently ruin a run.

`action_type="env"`. MinecraftSim defaults to `"agent"`, the factored button/camera
encoding VPT and STEVE-1 emit. This agent writes ordinary action dicts, so it needs the
`"env"` space -- and passing the wrong one does not raise, it goes through
`agent_action_to_env_action` and produces garbage actions that look plausible in the log.

`MINESTUDIO_DIR`. `check_engine()` runs at *class definition* time in
`minestudio/simulator/entry.py` and calls `input()` when the engine jar is missing. In a
batch job with no stdin that is an EOFError at import, before any of this module's code
runs -- so the variable is set here, at import, rather than left to the launcher.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Before any minestudio import; see the module docstring.
os.environ.setdefault("MINESTUDIO_DIR", "/n/netscratch/sham_lab/Lab/chloe00/MineStudio")

from loguru import logger  # noqa: E402

TASKS = {
    "diamond": {
        "yaml": "MCU_benchmark/task_configs/longterm/mine_diamond_from_scratch.yaml",
        "name": "mine_diamond_from_scratch",
        "default_steps": 6000,
    },
    "dragon": {
        "yaml": "MCU_benchmark/task_configs/longterm/kill_ender_dragon.yaml",
        "name": "kill_ender_dragon",
        "default_steps": 12000,
    },
}


def load_task(path: str | Path) -> tuple[list[str], dict[str, str], list[dict[str, Any]]]:
    """(init commands, task dict, milestone config). Both long-horizon configs carry an
    empty `custom_init_commands` -- they start from nothing, which is the point -- so the
    commands list is normally empty and CommandsCallback is skipped."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    commands = data.get("custom_init_commands") or []
    task = {"name": Path(path).stem, "text": data.get("text", "")}
    return commands, task, data.get("milestone_reward_cfg") or []


def make_sim(task_yaml: str | Path, output_dir: str | Path, *, fps: int = 20,
             obs_size: tuple[int, int] = (128, 128),
             render_size: tuple[int, int] = (640, 360),
             record: bool = True, fast_reset: bool = True):
    """The simulator plus the callbacks the official scoring needs.

    `MilestoneTrackerCallback` is registered even though this package keeps its own
    `MilestoneLedger`: the callback writes `milestone_tracking.json` in the exact format
    the RDI-Foundation runner produces, so a run here is directly comparable to their
    VPT/STEVE-1 baselines. The ledger and the callback read the same statistics through
    the same delta rule, so they cannot disagree.
    """
    # Adds `drop`, the one engine-supported verb HumanSurvival leaves out. Must run
    # before MinecraftSim is constructed, since the spec is read in its __init__.
    from mcu_worldmodel.craft_env import patch_minecraft_sim
    patch_minecraft_sim()

    from minestudio.simulator import MinecraftSim
    from minestudio.simulator.callbacks import (
        CommandsCallback, RecordCallback, FastResetCallback,
    )
    import sys
    sys.path.insert(0, str(Path("MCU_benchmark").resolve()))
    from utility.milestone_tracker import MilestoneTrackerCallback
    from utility.task_call import TaskCallback

    commands, task, milestone_cfg = load_task(task_yaml)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    callbacks = [
        TaskCallback(task),
        MilestoneTrackerCallback(reward_cfg=milestone_cfg, output_path=output_dir,
                                 task_name=task["name"]),
    ]
    if fast_reset:
        # The from-scratch tasks need a survivable start with trees; without this the
        # spawn can be ocean or desert and the first milestone (mine a log) is
        # unreachable for reasons that have nothing to do with the agent.
        callbacks.append(FastResetCallback(biomes=["plains", "forest"],
                                           random_tp_range=1000))
    if record:
        callbacks.append(RecordCallback(record_path=str(output_dir), fps=fps,
                                        frame_type="pov"))
    if commands:
        callbacks.insert(0, CommandsCallback(commands))
        logger.info(f"[env] {len(commands)} init command(s)")

    logger.info(f"[env] task={task['name']} milestones={len(milestone_cfg)}")
    sim = MinecraftSim(
        action_type="env",          # see the module docstring
        obs_size=obs_size,
        render_size=render_size,
        callbacks=callbacks,
    )
    return sim, task, milestone_cfg
