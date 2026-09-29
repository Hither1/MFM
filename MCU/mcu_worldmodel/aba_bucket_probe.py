r"""Live test: does filling a bucket move the `use_item` / `bucket` statistic?

`aba_water_log_water` scores its first and third goals on `use_item` of `bucket`. The
statistic exists in the 1.16 registry (`use_item.bucket`, minerl_keys ["use_item",
"bucket"]) -- but "the key exists" and "filling a bucket increments it in this engine and
reaches `info`" are different claims, and only the engine settles the second. Getting it
wrong costs a whole wave: the arms would run 12,000 steps against a goal that can never
fire, and score 0/3 for a reason that has nothing to do with memory.

"Did the statistic move" is necessary but NOT sufficient, which the first run of this
probe (job 44955980) showed: `use_item.bucket` went 0 -> 1 while the inventory still held
an empty `bucket`. That has two readings and they are opposites --

    the fill worked and a later click emptied it again   -> the rule is sound
    the counter moves on ANY right-click holding a bucket -> the goal is satisfiable in
                                                             one click, anywhere, and the
                                                             task measures nothing

so the probe now separates them: click with a bucket and no water in reach FIRST, and
only then flood and click. A counter that moves in phase A settles it the wrong way.

Also checks the two things the same wave depends on and which nothing else exercises
live: that the ABA task config loads through the green agent's own loaders, and that
CommandsCallback actually delivers the bucket.

Writes JSON to stdout and to --out. Exit 0 only if the statistic moved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

TASK = "aba_water_log_water"


def _stat(info: dict, event: str, obj: str) -> float:
    bucket = info.get(event) or {}
    val = bucket.get(obj, 0)
    return float(val.item()) if hasattr(val, "item") else float(val or 0)


def _inventory(info: dict) -> dict:
    return {k: v.get("type") for k, v in (info.get("inventory") or {}).items()
            if isinstance(v, dict) and v.get("type") not in (None, "air", "none")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("output/aba_bucket_probe.json"))
    ap.add_argument("--task", default=TASK)
    args = ap.parse_args(argv)

    out: dict = {"task": args.task, "used_bucket_fired": False, "error": None}

    # 1. the plumbing, through the loaders the green agent itself uses
    from util import get_tasks, load_world_spec
    from task_milestones import load_milestone_cfg, load_reveal_mode

    tasks = {t[0]: t for t in get_tasks(args.task)}
    name, commands, text, _reward, milestones = tasks[args.task]
    out["config"] = {
        "commands": commands,
        "world_spec": load_world_spec(args.task),
        "reveal": load_reveal_mode(args.task),
        "goals": [c["identity"] for c in load_milestone_cfg(args.task)],
        "rule_0": load_milestone_cfg(args.task)[0],
    }

    from mcu_worldmodel.craft_env import patch_minecraft_sim
    from mcu_worldmodel.procedures import act, noop
    patch_minecraft_sim()
    from minestudio.simulator import MinecraftSim
    from minestudio.simulator.callbacks import CommandsCallback

    sim = None
    try:
        sim = MinecraftSim(action_type="env", obs_size=(128, 128),
                           render_size=(640, 360),
                           callbacks=[CommandsCallback(commands)],
                           **load_world_spec(args.task))
        obs, info = sim.reset()
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())

        # 2. did CommandsCallback deliver the bucket?
        inv = _inventory(info)
        out["inventory_after_reset"] = inv
        out["bucket_given"] = any(v == "bucket" for v in inv.values())
        if not out["bucket_given"]:
            out["error"] = "CommandsCallback did not deliver the bucket"
            return 1

        def snapshot(label):
            return {"phase": label,
                    "use_item.bucket": _stat(info, "use_item", "bucket"),
                    "use_item.water_bucket": _stat(info, "use_item", "water_bucket"),
                    "inventory": _inventory(info)}

        def click(n=3):
            nonlocal obs, info
            for _ in range(n):
                obs, _, _, _, info = sim.step(act(use=1))
                obs, _, _, _, info = sim.step(noop())

        phases = []
        phases.append(snapshot("start"))

        # --- A. the control. A bucket in hand and NO water in reach. If the counter
        # moves here, the goal is one right-click and the task is worthless.
        for pitch in (-60.0, 60.0):          # sky, then ground
            obs, _, _, _, info = sim.step(act(camera=[pitch, 0.0]))
            click()
            phases.append(snapshot(f"no_water_pitch_{pitch:+.0f}"))
            obs, _, _, _, info = sim.step(act(camera=[-pitch, 0.0]))
        out["fires_without_water"] = (
            phases[-1]["use_item.bucket"] > phases[0]["use_item.bucket"])

        # --- B. flood, then ONE click. `/fill` rather than finding a pond: this probe is
        # about the statistic, not about navigation.
        for cmd in ("/fill ~-3 ~-1 ~-3 ~3 ~-1 ~3 minecraft:water",
                    "/fill ~-3 ~ ~-3 ~3 ~1 ~3 minecraft:air"):
            sim.env.execute_cmd(cmd)
        for _ in range(10):
            obs, _, _, _, info = sim.step(noop())
        phases.append(snapshot("flooded"))
        before = _stat(info, "use_item", "bucket")

        fills = []
        for pitch in (30.0, 20.0, 15.0, 25.0, 40.0):
            obs, _, _, _, info = sim.step(act(camera=[pitch, 0.0]))
            click(1)
            snap = snapshot(f"fill_pitch_{pitch:+.0f}")
            fills.append(snap)
            if snap["use_item.bucket"] > before:
                break
            obs, _, _, _, info = sim.step(act(camera=[-pitch, 0.0]))
        phases.extend(fills)

        # --- C. one more click empties it again: that is what `use_item.water_bucket`
        # counts, and it is why the second goal needs a genuine second trip to water.
        click(1)
        phases.append(snapshot("after_emptying"))

        out["phases"] = phases
        out["used_bucket_before"] = before
        out["used_bucket_after"] = _stat(info, "use_item", "bucket")
        filled = [p for p in fills if p["use_item.bucket"] > before]
        out["water_bucket_in_inventory"] = bool(filled) and any(
            v == "water_bucket" for v in filled[-1]["inventory"].values())
        # Green only if the counter moved ON a fill and stayed put without water.
        out["used_bucket_fired"] = (
            bool(filled) and not out["fires_without_water"]
            and out["water_bucket_in_inventory"])
        out["inventory_final"] = _inventory(info)
        out["use_item_keys"] = sorted((info.get("use_item") or {}).keys())
    except Exception as exc:  # noqa: BLE001 - the report is the deliverable
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))

    return 0 if out["used_bucket_fired"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
