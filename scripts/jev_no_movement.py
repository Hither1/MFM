#!/usr/bin/env python
"""Prove the jev arm moved nothing: drive the OTHER arms under two MCU checkouts and diff.

The gen-4 chassis is shared, so a new arm is only admissible if the arms already on
record are byte-identical with it in the tree (`fairness-invariants`). The pins in
`tests/pins/` are recorded against the MCU vintage this MFM tree pairs with, which is not
the checkout the gen-4 arms launch from -- so this compares the two checkouts directly
instead: the same fakes, the same steps, under each `sys.path`, in a subprocess each
(two copies of `mcu_worldmodel` cannot share one interpreter).

    python scripts/jev_no_movement.py <baseline MCU> <MCU with the arm>

What is compared, for every arm but jev: the system prompt each mode renders, and the
logbook and mfm arms driven 120 steps -- `logs.txt`, `AGENTS.md`, every turn prompt, and
every action sent to the game.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MODES = ("worldmodel", "logbook", "wmlite", "direct", "mfm")
DRIVEN = ("logbook", "mfm")


def digest(mcu_root: str) -> dict:
    """Run inside the subprocess: import this checkout and render everything."""
    sys.path.insert(0, mcu_root)
    for key in [k for k in os.environ if k.startswith(("CODEX_", "PROLONG_", "FAKE_CODEX_"))]:
        os.environ.pop(key, None)
    os.environ["HOME"] = "/nonexistent-home"

    import numpy as np
    from mcu_worldmodel import prompts
    from mcu_worldmodel.agent import WorldModelAgent
    from mcu_worldmodel.milestones import MilestoneLedger
    from mcu_worldmodel.selftest import FakeCodex, fake_info

    kw = dict(task_text="get a log", progress_block="0/2", entry_cap=20, step_cap=400,
              platform_prompt="HOST REFERENCE", graph_summary="", plan_summary="",
              discipline_summary="")
    out: dict = {"prompts": {}}
    for mode in MODES:
        try:
            text = prompts.act_prompt(**kw, memory_mode=mode)
        except TypeError:                       # an older signature: drop the extras
            text = prompts.act_prompt(task_text="get a log", progress_block="0/2",
                                      entry_cap=20, step_cap=400,
                                      platform_prompt="HOST REFERENCE", memory_mode=mode)
        out["prompts"][mode] = hashlib.sha256(text.encode()).hexdigest()

    cfg = [{"event": "mine_block", "identity": "mine_log", "objects": ["oak_log"],
            "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "crafting_table",
            "objects": ["crafting_table"], "reward": 1.0, "max_reward_times": 1},
           {"event": "craft_item", "identity": "iron_pickaxe",
            "objects": ["iron_pickaxe"], "reward": 1.0, "max_reward_times": 1}]
    script = [
        {"actions": {"actions": [{"action": {"forward": 1}, "repeat": 5},
                                 {"action": {"attack": 1}, "repeat": 3}]},
         "message": "briefing one\n[PLAN]\nwalk then chop"},
        {"message": "no actions this time"},
        {"actions": {"actions": [{"procedure": "dig_down", "args": {"n": 4}}]},
         "message": "briefing two\n[PLAN]\ndig"},
    ] + [{"actions": {"actions": [{"action": {"attack": 1}, "repeat": 6}]},
          "message": f"[PLAN]\nchop {i}"} for i in range(20)]

    for mode in DRIVEN:
        root = Path(tempfile.mkdtemp(prefix=f"nomove_{mode}_"))
        agent = WorldModelAgent(workspace=root / "ws", task_text="get a log, a table, an "
                                "iron pickaxe", ledger=MilestoneLedger(cfg, "t"),
                                step_cap=50, memory_mode=mode,
                                platform_prompt="HOST REFERENCE")
        agent.codex = FakeCodex(agent.memory.root, [dict(s) for s in script])
        info = fake_info(inventory={"oak_log": 1})
        info["pov"] = np.zeros((360, 640, 3), dtype=np.uint8)
        agent.start(info)
        actions = []
        for step in range(1, 121):
            actions.append(agent.next_action(info))
            info = fake_info(inventory={"oak_log": 2 if step > 8 else 1},
                             mine_block={"oak_log": 1} if step > 8 else {})
            info["location_stats"]["xpos"] = np.array(1.0 + 0.3 * step)
            info["location_stats"]["ypos"] = np.array(64.0 - (step // 20))
            info["health"] = np.array(20.0 - (step // 25))
            info["pov"] = np.zeros((360, 640, 3), dtype=np.uint8)
            agent.observe(info, step)
        ws = agent.memory.root
        out[mode] = {
            "logs": _norm((ws / "logs.txt").read_text(), root),
            "agents_md": _norm((ws / "AGENTS.md").read_text(), root),
            "turn_prompts": [_norm(p, root) for p in agent.codex.prompts],
            "actions": json.dumps([{k: (v.tolist() if hasattr(v, "tolist") else v)
                                    for k, v in a.items()} for a in actions],
                                  sort_keys=True),
        }
    return out


def _norm(text: str, root: Path) -> str:
    return text.replace(str(root), "<ROOT>")


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--digest":
        Path(sys.argv[3]).write_text(json.dumps(digest(sys.argv[2]), indent=1))
        return 0
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    outs = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, root in enumerate(sys.argv[1:3]):
            path = Path(tmp) / f"digest{i}.json"
            proc = subprocess.run([sys.executable, __file__, "--digest", root, str(path)],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                print(proc.stdout[-4000:], proc.stderr[-4000:])
                return 1
            outs.append(json.loads(path.read_text()))
    a, b = outs
    bad = []
    for mode, sha in a["prompts"].items():
        if b["prompts"].get(mode) != sha:
            bad.append(f"the {mode} system prompt changed")
    for mode in DRIVEN:
        for key in a[mode]:
            if a[mode][key] != b[mode].get(key):
                bad.append(f"the {mode} arm's {key} changed")
    for line in bad:
        print("MOVED:", line)
    if not bad:
        print(f"unchanged: {len(a['prompts'])} system prompts, "
              f"{len(DRIVEN)} arms driven 120 steps (logs, AGENTS.md, prompts, actions)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
