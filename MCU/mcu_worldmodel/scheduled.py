"""Commands fired at chosen steps, so a landmark can stop existing mid-episode.

The recall probes need something the agent saw early and *cannot see now*. A landmark that
is still standing when the goal arrives is findable by looking around, and then the task
measures perception rather than memory -- MrSteve's burning zombies matter precisely
because they have burned away by the time you are asked to go back to where they were.

`custom_init_commands` only fire at reset, so removing something later needs this. Nothing
here reads the agent or the ledger: it is a wall clock in steps, identical for every arm.
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

try:  # pragma: no cover - exercised by which environment imports this
    from minestudio.simulator.callbacks.callback import MinecraftCallback
except Exception:  # noqa: BLE001
    # The offline test suite runs without the engine (no gym3, no JVM), and every other
    # module here is importable that way -- `milestones`, `agent` and the rest pull in
    # nothing from minestudio at import time. `entry.py` only ever uses MinecraftCallback
    # as a type annotation on `MinecraftSim(callbacks=...)`; the simulator calls the three
    # hooks by name and never isinstance-checks, so a stand-in base costs nothing at
    # runtime and keeps the scheduling logic unit-testable.
    class MinecraftCallback:  # type: ignore[no-redef]
        pass


class ScheduledCommandsCallback(MinecraftCallback):
    """Run `commands` when the episode reaches `step`.

    :param schedule: [{"step": 500, "commands": ["/fill ...", ...]}, ...]
    """

    def __init__(self, schedule: list[dict[str, Any]]) -> None:
        super().__init__()
        self.schedule = sorted((dict(s) for s in (schedule or [])),
                               key=lambda s: int(s.get("step", 0)))
        self.step = 0
        self.origin: tuple[int, int, int] | None = None
        self.fired: list[dict[str, Any]] = []

    def after_reset(self, sim, obs, info):
        self.step = 0
        self.fired = []
        # Where the episode began. `~` is useless here: it resolves against the player's
        # position at the moment the command runs, and the whole point of a scheduled
        # command is that it runs hundreds of steps later, by which time the agent has
        # walked away. A landmark removed at `~` would be removed from wherever the agent
        # happens to be standing, and would still be burning where it was left.
        loc = info.get("location_stats") or {}

        def coord(*names):
            for n in names:
                if n in loc:
                    v = loc[n]
                    return int(round(float(v.item() if hasattr(v, "item") else v)))
            return None

        x, y, z = coord("xpos", "x"), coord("ypos", "y"), coord("zpos", "z")
        self.origin = (x, y, z) if None not in (x, y, z) else None
        if self.origin is None and self.schedule:
            logger.warning("[scheduled] no location_stats at reset: {x}/{y}/{z} "
                           "placeholders cannot be resolved")
        else:
            logger.info(f"[scheduled] origin={self.origin} for {len(self.schedule)} entries")
        return obs, info

    #: `{x}`, `{z-4}`, `{y+2}` -- an axis of the episode's start position, plus an
    #: optional offset. The offset has to be inside the braces and done here: `{x}-4`
    #: would substitute to the string "123-4", which Minecraft rejects as a coordinate.
    _PLACEHOLDER = re.compile(r"\{([xyz])\s*([+-]\s*\d+)?\}")

    def resolve(self, command: str) -> str:
        """Substitute the episode's start coordinates into a command.

        A regex over `{axis[+-]offset}` rather than `str.format`: Minecraft commands are
        full of literal braces (`/give @s minecraft:shovel{Enchantments:[{id:"...",lvl:1}]}`)
        and `format` would raise on every one of them.
        """
        if self.origin is None:
            return command
        axes = dict(zip("xyz", self.origin))

        def one(m: "re.Match[str]") -> str:
            offset = int((m.group(2) or "0").replace(" ", ""))
            return str(axes[m.group(1)] + offset)

        return self._PLACEHOLDER.sub(one, command)

    def after_step(self, sim, obs, reward, terminated, truncated, info):
        self.step += 1
        for entry in self.schedule:
            at = int(entry.get("step", 0))
            if at != self.step:
                continue
            for command in entry.get("commands") or []:
                command = self.resolve(command)
                try:
                    sim.env.execute_cmd(command)
                except Exception as exc:  # a landmark that will not die must not kill the run
                    logger.warning(f"[scheduled] step {at}: {command!r} failed: {exc}")
            self.fired.append({"step": at, "commands": list(entry.get("commands") or [])})
            logger.info(f"[scheduled] step {at}: ran {len(entry.get('commands') or [])} command(s)")
        return obs, reward, terminated, truncated, info

    def __repr__(self) -> str:
        return f"ScheduledCommandsCallback(entries={len(self.schedule)})"
