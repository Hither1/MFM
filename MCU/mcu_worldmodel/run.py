"""CLI: run one long-horizon MCU task with the world-model agent.

    python -m mcu_worldmodel.run --task diamond --steps 6000 --output outputs/d1

The episode loop is deliberately thin. Everything interesting -- when to think, what to
remember, when to re-compile the world model -- lives in the agent; this file only steps
the simulator and keeps the two halves in sync. That is the same division MineExplorer's
`eval_benchmark.py` draws, and it is what lets the agent be swapped for a baseline without
touching the harness.
"""
from __future__ import annotations

import getpass
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

os.environ.setdefault("MINESTUDIO_DIR", f"/n/netscratch/sham_lab/Lab/{getpass.getuser()}/MineStudio")

from loguru import logger  # noqa: E402

from mcu_worldmodel.agent import WorldModelAgent  # noqa: E402
from mcu_worldmodel.env import TASKS, make_sim  # noqa: E402
from mcu_worldmodel.milestones import MilestoneLedger  # noqa: E402

_stop = False
#: Set once the simulator exists, so the signal handler can flush without the loop's help.
_SIM = None
_STEP = 0


def _sigint(signum, frame):
    """Flush the scoreable artefacts IMMEDIATELY, then ask the loop to stop.

    Flushing here rather than leaving it to the `finally` block, because deferring does not
    survive `scancel`. Slurm sends SIGTERM and then SIGKILL after a short grace period,
    while this loop spends 30-90s at a time blocked inside a `codex exec` subprocess -- so
    a handler that merely sets a flag is still waiting for the turn to return when SIGKILL
    arrives. Measured: the cancelled dragon_v3 logged "signal 15 received" and still wrote
    no video and no milestone JSON.

    Python delivers signals to the main thread and runs the handler even while it is
    blocked on a subprocess, so doing the I/O here does reach disk. Every step is guarded:
    a failure while shutting down must not mask the shutdown.
    """
    global _stop
    logger.warning(f"signal {signum} received; flushing video + milestone JSON now")
    try:
        if _SIM is not None:
            _flush_recorder(_SIM, _STEP)
            for cb in getattr(_SIM, "callbacks", []):
                if type(cb).__name__ == "MilestoneTrackerCallback":
                    cb.before_close(_SIM)
                    logger.info("[run] milestone JSON written from the signal handler")
    except Exception as e:
        logger.error(f"[run] emergency flush failed: {e}")
    _stop = True


def _flush_recorder(sim, step: int) -> None:
    """Force RecordCallback to write its buffer to a numbered mp4 and start a new one."""
    for cb in getattr(sim, "callbacks", []):
        if type(cb).__name__ != "RecordCallback":
            continue
        try:
            n = len(getattr(cb, "frames", []))
            if n:
                cb._save_episode()
                logger.info(f"[run] flushed {n} recorded frames at step {step}")
        except Exception as e:      # never let recording bookkeeping kill an episode
            logger.warning(f"[run] could not flush the recorder at step {step}: {e}")


def run(args: argparse.Namespace) -> dict:
    task_cfg = TASKS[args.task]
    steps = args.steps or task_cfg["default_steps"]
    out = Path(args.output or f"outputs/{args.task}_worldmodel").resolve()
    out.mkdir(parents=True, exist_ok=True)

    sim, task, milestone_cfg = make_sim(
        task_cfg["yaml"], out, fps=args.fps, record=not args.no_record,
        fast_reset=not args.no_fast_reset,
    )
    ledger = MilestoneLedger(milestone_cfg, task_name=task["name"])
    agent = WorldModelAgent(
        workspace=out / "memory",
        task_text=task["text"],
        ledger=ledger,
        model=args.model,
        reasoning_effort=args.effort,
        base_url=args.base_url or None,
        codex_home=args.codex_home or None,
        transcript_dir=out / "codex_turns",
        step_cap=args.step_cap,
        extended_actions=True,
    )

    global _SIM
    _SIM = sim
    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)
    logger.info(f"[run] {task['name']}  steps={steps}  milestones={len(milestone_cfg)}")
    started = time.time()
    obs, info = sim.reset()
    agent.start(info)

    step = 0
    try:
        global _STEP
        for step in range(1, steps + 1):
            _STEP = step
            if _stop:
                break
            action = agent.next_action(info)
            obs, reward, terminated, truncated, info = sim.step(action)
            agent.observe(info, step)
            if terminated:
                logger.info(f"[run] episode terminated by the environment at step {step}")
                break
            if args.flush_every and step % args.flush_every == 0:
                # Write out what has been recorded so far. RecordCallback holds every
                # frame in memory (0.69 MB each at 640x360), so a 12,000-step episode
                # would otherwise carry ~8 GB and lose all of it on a kill. Flushing
                # produces numbered chunks that can be concatenated, and caps the buffer.
                _flush_recorder(sim, step)
            if step % 500 == 0:
                logger.info(f"[run] step {step}  {ledger.progress_line()}  "
                            f"turns={agent.turns}")
            if ledger.all_done():
                logger.success(f"[run] all milestones verified at step {step}")
                break
    finally:
        # before_close is what writes milestone_tracking.json, so it must run even on a
        # crash -- a failed episode's partial progress is the measurement.
        try:
            sim.close()
        except Exception as e:
            logger.warning(f"[run] sim.close failed: {e}")
        agent.step = step
        report = agent.report()
        report["wall_seconds"] = round(time.time() - started, 1)
        agent.save_report(out / "worldmodel_report.json")
        logger.info(json.dumps(report["milestones"], indent=2))
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--task", required=True, choices=sorted(TASKS))
    p.add_argument("--steps", type=int, default=None,
                   help="env steps (default: 6000 diamond / 12000 dragon)")
    p.add_argument("--output", default=None)
    p.add_argument("--model", default="gpt-5.6-sol")
    p.add_argument("--effort", default="medium",
                   choices=["none", "low", "medium", "high", "xhigh"])
    p.add_argument("--base-url", default="", help="local OpenAI-compatible server")
    p.add_argument("--codex-home", default="")
    p.add_argument("--step-cap", type=int, default=400,
                   help="max env ticks one turn's plan may run")
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--no-record", action="store_true")
    p.add_argument("--flush-every", type=int, default=1000,
                   help="write recorded video to disk every N steps (0 disables). Bounds "
                        "RecordCallback's in-memory frame buffer and makes a killed run "
                        "still scoreable.")
    p.add_argument("--no-fast-reset", action="store_true")
    args = p.parse_args()

    try:
        report = run(args)
    except Exception:
        logger.exception("[run] failed")
        sys.exit(1)
    m = report["milestones"]
    print(f"\n{m['milestones_achieved']}/{m['total_milestones']} milestones "
          f"({m['completion_rate']*100:.0f}%) in {report['steps']} steps, "
          f"{report['turns']['act']} act turns")


if __name__ == "__main__":
    main()
