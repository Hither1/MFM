"""Stage-test rig: the real runner against the standalone simulator, no model.

The verification gap this closes: a macro's tick logic could be unit-tested against a
synthetic screen (selftest.py) and then only ever met the real GUI, the real block
physics and the real statistics inside a 12,000-step arm with a model in the loop --
hours per attempt, one attempt per night, the failure buried in a 700-entry log. Here
the SAME `WorldModelAgent` (queue, cursor, guards, notes) runs against `MinecraftSim`
with a scripted backend: a stage script prepares a world state with commands the
evaluation never allows (/give, /tp, /setblock, /execute in the_nether), hands the
runner one plan at a time, and asserts on inventory, statistics and position. A
whole stage of the dragon chain -- "diamond pickaxe in hand, a lava lake ahead, make
and mine obsidian, build and light the portal, enter" -- is testable in minutes from
a prepared state, and every macro gets exercised where it has to work.

Run a stage from the repo root with the engine environment loaded:

    source ./env.sh; xvfb-run -a .venv/bin/python -m mcu_worldmodel.stages.s1_gui

The scripted backend answers act turns with the plan the stage pushed; when the plan
drains the stage regains control before another turn fires, so a stage is a sequence
of (prepare, run one plan, assert) steps. Notes the runner writes are captured per run
and are part of the evidence: a macro that fails must SAY so in a note.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DRAGON_YAML = ROOT / "MCU_benchmark" / "task_configs" / "longterm" / "kill_ender_dragon.yaml"
SPAWN = (-3009.5, 71.0, -5572.5)


class ScriptedCodex:
    """Stands in for CodexTurn: serves the plans a stage pushes, in order."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.script: list[dict[str, Any]] = []
        self.calls = 0
        self.served = 0          # real plans handed out (fillers not counted)
        self.session_max_turns = 1

    def push(self, entries: list[dict[str, Any]], message: str = "") -> None:
        self.script.append({"actions": {"actions": entries},
                            "message": message or "[PLAN]\nstage plan"})

    def write_system_prompt(self, text: str) -> None:
        (self.workspace / "AGENTS.md").write_text(text, encoding="utf-8")

    def run(self, prompt: str, images=(), *, expect_actions: bool = True) -> dict:
        self.calls += 1
        from mcu_worldmodel.codex_backend import TURN_ARTEFACTS
        for stale in TURN_ARTEFACTS:
            (self.workspace / stale).unlink(missing_ok=True)
        if self.script:
            turn = self.script.pop(0)
            self.served += 1
        else:
            # The runner fires the next turn the moment a plan drains; with nothing
            # scripted it would retry (with sleeps) and log a failed turn. A one-tick
            # no-op hands control back to the stage instead.
            turn = {"actions": {"actions": [{"action": {}, "repeat": 1}]},
                    "message": "[PLAN]\nfiller"}
        return {"actions_json": json.dumps(turn["actions"]),
                "message": turn.get("message", ""), "ok": True,
                "error": None, "overflow": False}

    def read_outputs(self) -> dict:
        return {"hypotheses_ops": None, "claim": None, "errors": []}

    @staticmethod
    def split_briefing(message: str):
        from mcu_worldmodel.codex_backend import CodexTurn
        return CodexTurn.split_briefing(message)

    def vision_audit(self) -> dict:
        return {"frames_attached": 0, "view_image_calls": 0}


class Rig:
    def __init__(self, out: str | Path, *, task_yaml: str | Path = DRAGON_YAML,
                 step_cap: int = 400, max_steps: int = 30000) -> None:
        from minestudio.simulator import MinecraftSim
        from mcu_worldmodel.agent import WorldModelAgent
        from mcu_worldmodel.env import load_task
        from mcu_worldmodel.milestones import MilestoneLedger

        self.out = Path(out)
        (self.out / "memory").mkdir(parents=True, exist_ok=True)
        _, task, cfg = load_task(task_yaml)
        t0 = time.time()
        self.sim = MinecraftSim(action_type="env", obs_size=(640, 360),
                                render_size=(640, 360), callbacks=[])
        self.agent = WorldModelAgent(
            workspace=self.out / "memory", task_text=task["text"],
            ledger=MilestoneLedger(cfg, task["name"]),
            step_cap=step_cap, max_steps=max_steps, memory_mode="logbook",
            extended_actions=False)
        self.codex = ScriptedCodex(self.agent.memory.root)
        self.agent.codex = self.codex
        self.notes: list[str] = []
        _orig = self.agent.memory.add_note

        def _capture(note: str) -> None:
            self.notes.append(note)
            _orig(note)
        self.agent.memory.add_note = _capture  # type: ignore[method-assign]
        self.step = 0
        self.info: dict = {}
        self.failures: list[str] = []
        self.checks = 0
        self.log(f"sim + agent constructed in {time.time() - t0:.0f}s")

    # -- lifecycle ---------------------------------------------------------

    def log(self, msg: str) -> None:
        print(f"[rig] {msg}", flush=True)

    def reset(self) -> None:
        t0 = time.time()
        _, self.info = self.sim.reset()
        self.agent.start(self.info)
        self.log(f"reset in {time.time() - t0:.0f}s at {self.pos()}")

    def close(self) -> None:
        try:
            self.sim.close()
        except Exception:
            pass

    # -- world preparation ---------------------------------------------------

    def cmd(self, command: str, settle: int = 4) -> None:
        self.sim.env.execute_cmd(command)
        self.idle(settle)

    def give(self, item: str, n: int = 1) -> None:
        self.cmd(f"/give @a minecraft:{item} {int(n)}")

    def clear(self) -> None:
        self.cmd("/clear")

    def tp(self, x: float, y: float, z: float, yaw: float = 0.0, pitch: float = 0.0) -> None:
        self.cmd(f"/tp @a {x} {y} {z} {yaw} {pitch}", settle=8)

    def platform(self, x: float, y: float, z: float, r: int = 4, block: str = "stone",
                 clear_to: int = 6) -> None:
        """A flat `block` floor at `y` and air above it, centred on (x, z)."""
        x0, z0 = int(np.floor(x)), int(np.floor(z))
        self.cmd(f"/fill {x0 - r} {int(y)} {z0 - r} {x0 + r} {int(y)} {z0 + r} "
                 f"minecraft:{block}")
        self.cmd(f"/fill {x0 - r} {int(y) + 1} {z0 - r} {x0 + r} {int(y) + clear_to} "
                 f"{z0 + r} minecraft:air")

    def setblock(self, x: int, y: int, z: int, block: str) -> None:
        self.cmd(f"/setblock {int(x)} {int(y)} {int(z)} minecraft:{block}")

    def fill(self, x0: int, y0: int, z0: int, x1: int, y1: int, z1: int,
             block: str = "air") -> None:
        self.cmd(f"/fill {int(x0)} {int(y0)} {int(z0)} {int(x1)} {int(y1)} {int(z1)} "
                 f"minecraft:{block}")

    def summon(self, mob: str, x: float, y: float, z: float, noai: bool = True,
               extra: str = "") -> None:
        """A mob at an absolute position. NoAI keeps it where it was put -- a stage
        asserts against a target that does not wander. Coordinates are ABSOLUTE
        floats: `/summon` with `~` is relative to the player, and int() of a
        negative coordinate rounds toward zero (one block off) -- use math.floor
        for block coordinates."""
        nbt = "{NoAI:1b" + (("," + extra) if extra else "") + "}" if noai else (
            "{" + extra + "}" if extra else "")
        self.cmd(f"/summon minecraft:{mob} {x} {y} {z} {nbt}")

    def kill(self, mob: str) -> None:
        self.cmd(f"/kill @e[type=minecraft:{mob}]")

    def stats(self) -> dict[str, dict[str, float]]:
        """Every non-zero statistic bucket entry as floats: {event: {item: n}}."""
        out: dict[str, dict[str, float]] = {}
        for k in ("mine_block", "craft_item", "pickup", "use_item", "break_item",
                  "kill_entity", "damage_dealt", "custom"):
            b = self.info.get(k)
            if not isinstance(b, dict):
                continue
            row = {}
            for i, v in b.items():
                f = float(v.item()) if hasattr(v, "item") else float(v)
                if f > 0:
                    row[str(i)] = f
            if row:
                out[k] = row
        return out

    @staticmethod
    def stat_delta(before: dict, after: dict) -> dict[str, float]:
        """{"event.item": delta} for every bucket entry that moved."""
        out: dict[str, float] = {}
        for k in set(before) | set(after):
            for i in set(before.get(k, {})) | set(after.get(k, {})):
                d = after.get(k, {}).get(i, 0.0) - before.get(k, {}).get(i, 0.0)
                if d:
                    out[f"{k}.{i}"] = d
        return out

    # -- stepping ------------------------------------------------------------

    def _step(self, action: dict[str, Any]) -> None:
        _, _, _, _, self.info = self.sim.step(action)
        self.step += 1
        self.agent.observe(self.info, self.step)

    def idle(self, ticks: int) -> None:
        """Ticks with nothing pressed, observed by the agent (no turn is fired)."""
        for _ in range(int(ticks)):
            self._step(self.sim.noop_action())

    def run(self, entries: list[dict[str, Any]], max_ticks: int = 1500,
            label: str = "", settle: int = 8) -> dict[str, Any]:
        """Hand the runner one plan and step until it drains (or `max_ticks`)."""
        self.codex.push(entries)
        served0, notes0 = self.codex.served, len(self.notes)
        inv0 = dict(self.agent._cur_inv)
        cs0 = dict(self.agent.cursor_stats)
        t = 0
        while t < max_ticks:
            action = self.agent.next_action(self.info)
            self._step(action)
            t += 1
            if self.codex.served > served0 and not self.agent.queue:
                break
        # The inventory observation lags a GUI click by up to ~15 ticks (measured
        # 2026-09-03); a check that reads `inv` right after the queue drains would see
        # the previous state. These ticks are not part of the plan's cost.
        self.idle(settle)
        res = {"ticks": t, "notes": self.notes[notes0:], "inv": dict(self.agent._cur_inv),
               "delta": {k: self.agent._cur_inv.get(k, 0) - inv0.get(k, 0)
                         for k in set(inv0) | set(self.agent._cur_inv)
                         if self.agent._cur_inv.get(k, 0) != inv0.get(k, 0)},
               "gui": bool(self.info.get("isGuiOpen")), "screen": self.agent._screen,
               "pos": self.pos(), "drained": not self.agent.queue,
               "stats": {k: v - cs0.get(k, 0) for k, v in self.agent.cursor_stats.items()
                         if v != cs0.get(k, 0)}}
        name = label or ", ".join(e.get("procedure", "raw") for e in entries)
        self.log(f"run {name}: {t} ticks, delta {res['delta']}, gui={res['gui']} "
                 f"screen={res['screen']} stats={res['stats']}")
        for n in res["notes"]:
            self.log(f"   note: {n[:220]}")
        return res

    def ensure_closed(self) -> None:
        """Close whatever screen is open, dropping a held stack if it comes to that
        (a stage's later steps must not inherit an earlier failure's screen)."""
        if self.info.get("isGuiOpen"):
            self.run([{"procedure": "close_inventory", "args": {"force": True}}],
                     label="force close")

    # -- readings ------------------------------------------------------------

    def inv(self) -> dict[str, int]:
        return dict(self.agent._cur_inv)

    def stat(self, event: str, obj: str) -> float:
        from mcu_worldmodel.milestones import _stat
        return _stat(self.info, event, obj)

    def pos(self) -> dict[str, float] | None:
        from mcu_worldmodel.milestones import location
        p = location(self.info)
        return {k: round(v, 2) for k, v in p.items()} if p else None

    def frame(self, name: str) -> Path:
        from PIL import Image
        path = self.out / f"{name}.jpg"
        Image.fromarray(np.asarray(self.info["pov"])).save(path, quality=85)
        return path

    # -- assertions ----------------------------------------------------------

    def check(self, name: str, cond: Any, detail: Any = "") -> bool:
        self.checks += 1
        if cond:
            print(f"  ok   {name}", flush=True)
        else:
            print(f"  FAIL {name}  {detail}", flush=True)
            self.failures.append(name)
        return bool(cond)

    def summary(self) -> int:
        print(f"\n{self.checks} checks, {len(self.failures)} failed"
              + (": " + ", ".join(self.failures) if self.failures else ""), flush=True)
        return 1 if self.failures else 0


def P(name: str, **args) -> dict[str, Any]:
    """A procedure entry for `Rig.run`."""
    return {"procedure": name, "args": args}


def RAW(n: int = 1, **keys) -> dict[str, Any]:
    """A raw action entry held `n` ticks (`hotbar_3=1` -> `hotbar.3`)."""
    return {"action": {k.replace("hotbar_", "hotbar."): v for k, v in keys.items()},
            "repeat": int(n)}


def slot_of(rig: "Rig", item: str) -> int | None:
    """The first inventory slot holding `item`, or None."""
    inv = rig.info.get("inventory") or {}
    for s in range(36):
        e = inv.get(s) or inv.get(str(s))
        if isinstance(e, dict) and str(e.get("type")) == item:
            return s
    return None


def hotbar_of(rig: "Rig", item: str) -> int | None:
    """The hotbar NUMBER (1-9) holding `item`, or None when it is not in the hotbar."""
    s = slot_of(rig, item)
    return (s + 1) if s is not None and s <= 8 else None


def scratch_dir(stage: str) -> Path:
    base = os.environ.get("MCU_STAGE_OUT") or (ROOT / "logs" / "stages")
    out = Path(base) / f"{stage}_{time.strftime('%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def main_guard(fn) -> None:
    """Run a stage's `fn(rig)` with construction, reset and teardown handled."""
    stage = fn.__module__.rsplit(".", 1)[-1]
    if stage == "__main__":
        # `python -m mcu_worldmodel.stages.s1_gui` runs the module as __main__;
        # the output directory should still carry the stage's name.
        stage = Path(sys.argv[0]).stem
    out = scratch_dir(stage)
    print(f"[rig] stage {stage} -> {out}", flush=True)
    rig = Rig(out)
    code = 1
    try:
        rig.reset()
        fn(rig)
        code = rig.summary()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        rig.close()
    sys.exit(code)
