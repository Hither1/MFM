"""A live smoke test of the arc arm against the real coding-agent CLI.

The offline test drives everything through `tests/fake_arc_agent.py`; what only a real
run can show is that the CLI's sandbox lets `./act` write its request under the
workspace and read the answer, that the session reads the brief and acts through the
actuator rather than around it, and that a `view_image` lands. This runs the MCU
chassis in `--memory arc` on the selftest's synthetic world (no Minecraft) for a few
hundred ticks and prints the audit and what the actuator answered.

    python -m mfm.arc.smoke --out /var/tmp/arc-smoke-$USER [--agent codex|claude]
                            [--model gpt-5.6-sol] [--effort low] [--steps 300]

Auth: codex through `$CODEX_EVAL_HOME/auth.json` (default ~/.codex-eval), the way the
other arms' bare-binary path reads it; claude through its own login. Spends the
account's quota: run it on purpose.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np


def _pov(step: int) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = (step * 7) % 256
    frame[step % 360, :, 1] = 255
    frame[:, (step * 3) % 640, 2] = 200
    return frame


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="a directory under /var/tmp")
    ap.add_argument("--agent", default="codex", choices=["codex", "claude"])
    ap.add_argument("--model", default="gpt-5.6-sol")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--tick-timeout", type=int, default=240,
                    help="seconds the chassis waits per tick for a `./act do`")
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "MCU"))
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import fake_info

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1}]
    opts = {"agent": args.agent, "max_sessions": 3, "close_timeout": 20}
    if args.agent == "claude":
        opts["model"] = args.model
    agent = WorldModelAgent(
        workspace=out / "ws", task_text=(
            "SMOKE TEST of the harness, not a real world: the frames are synthetic. Get a "
            "log and a crafting table. Read the brief, then: run `./act status`, play ONE "
            "batch of two or three entries with a --plan, read the sections it printed, "
            "look at the frame it named with your image tool, write one line to notes.md, "
            "then play one more batch and stop."),
        ledger=MilestoneLedger(cfg, "smoke"), induction_every=0, step_cap=200,
        memory_mode="arc", platform_prompt="", codex_home=None,
        codex_timeout=args.tick_timeout, model=args.model, reasoning_effort=args.effort,
        arc_options=opts, transcript_dir=out / "sessions")
    info = fake_info(inventory={"oak_log": 1})
    info["pov"] = _pov(0)
    t0 = time.time()
    agent.start(info)
    for step in range(1, args.steps + 1):
        agent.next_action(info)
        info = fake_info(inventory={"oak_log": 2 if step > 40 else 1},
                         mine_block={"oak_log": 1} if step > 40 else {})
        info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
        info["pov"] = _pov(step)
        agent.observe(info, step)
        if agent.arc.batches_applied >= 2 and agent.arc.loop and not agent.arc.loop.alive:
            break
    agent.arc.finish()
    audit = agent.report()["arc"]
    print(json.dumps(audit, indent=1, default=str))
    calls = out / "ws" / ".act" / "calls.jsonl"
    if calls.exists():
        for line in calls.read_text().splitlines():
            d = json.loads(line)
            print(f"--- act {d['request'].get('argv')} rc={d['reply']['rc']}")
            print((d["reply"]["stdout"] or d["reply"]["stderr"])[:800])
    print(f"wall {time.time() - t0:.0f}s; sessions under {out / 'sessions'}")
    notes = out / "ws" / "notes.md"
    print("notes.md:", notes.read_text()[:300] if notes.exists() else "(none)")
    ok = audit["batches_applied"] >= 1 and audit["failure"] is None
    print("SMOKE", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
