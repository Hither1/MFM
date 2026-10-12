"""The host-side observer for the nether-portal case study.

One callback, added only to tasks whose config carries a `portal_probe:` block, so
every other task's callback list is byte-identical to what it was. It does three
things and no more:

  * asks the engine for the blocks around the player every `every` steps, and folds
    the answer into `portal.PortalTrace` -- the ground-truth record of which cell each
    obsidian block went into and when;
  * saves a PNG at each strike of the flint and steel, at the first moment a legal
    frame exists and at the first moment it is lit, because the failure this task
    measures is a geometric one and a number in a JSON file is not a check a person
    can make (a failed build shows a fire burning between scattered obsidian);
  * writes `portal_report.json` at close.

It never writes into `info`, never returns anything the agent can read, and the green
runner's `INFO_PASSTHROUGH` allowlist does not carry `voxels`, so the privileged view
stops here. That is deliberate and load-bearing: the question the task asks is whether
an agent knows where it put its blocks, and an environment that answers "your left
column is one short" has answered it for them.

Cost. A window of (-8, 9, -5, 6, -8, 9) is 3,179 cells; on a cleared stone pad the
engine reports the few hundred that are not air. At `every=10` that is two queries a
second of simulated time, which is far finer than a build takes and small enough that
a 12,000-step episode adds ~1,200 queries.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from loguru import logger

from mcu_worldmodel import portal
from mcu_worldmodel.milestones import location

try:  # pragma: no cover - depends on which environment imports this
    from minestudio.simulator.callbacks.callback import MinecraftCallback
except Exception:  # noqa: BLE001
    # Same reason as `mcu_worldmodel.scheduled`: the offline test suite has no engine,
    # and the simulator only ever calls these hooks by name.
    class MinecraftCallback:  # type: ignore[no-redef]
        pass


def _stat(info: dict, event: str, obj: str) -> float:
    bucket = info.get(event)
    if not isinstance(bucket, dict) or obj not in bucket:
        return 0.0
    v = bucket[obj]
    return float(v.item()) if hasattr(v, "item") else float(v)


class PortalProbeCallback(MinecraftCallback):
    """Watch a portal being built and write down where the blocks actually went.

    :param output_dir: where `portal_report.json` and the frames are written.
    :param window: voxel query box, engine convention `[x0, x1, y0, y1, z0, z1]`,
        offsets from the player's block position, upper bounds exclusive. The default
        reaches 8 blocks out horizontally and from 5 below to 5 above the feet, which
        covers a 5-tall frame whether the builder stands on the ground or on the
        4-block pillar `macros_nether.build_portal_frame` raises to reach the top row.
    :param every: env steps between queries.
    :param snapshots: save PNGs at ignitions and when a frame is first complete and
        first lit.
    """

    def __init__(self, output_dir: str | Path, window: list[int] | None = None,
                 every: int = 10, snapshots: bool = True) -> None:
        super().__init__()
        self.output_dir = Path(output_dir)
        self.window = tuple(window) if window else (-8, 9, -5, 6, -8, 9)
        if len(self.window) != 6:
            raise ValueError(f"portal_probe window needs 6 ints, got {self.window!r}")
        if max(abs(v) for v in self.window) > 50:
            # `VoxelAction`'s space is Box(-50, 50, [6]); a wider box is silently
            # clipped rather than refused, which would look like blocks vanishing.
            raise ValueError(f"portal_probe window exceeds the engine's +-50: {self.window}")
        self.every = max(1, int(every))
        self.snapshots = bool(snapshots)
        self.trace = portal.PortalTrace(window=self.window)
        self.step = 0
        self._prev: dict[str, Any] = {}
        #: Whether a voxel answer was ASKED for on the step now being read. Load-bearing:
        #: `MinecraftSim._wrap_obs_info` accumulates every key it has ever seen into one
        #: `self.info` dict and never clears it, so `info["voxels"]` survives from the
        #: step that requested it into every later step. Reading it again would fold a
        #: stale block list against a new player position and fill the map with blocks
        #: that were never there.
        self._asked = False
        #: Strikes of the flint and steel waiting to be scored, as {step, frame}. A
        #: strike is scored from the voxel answer of the step AFTER it, never from the
        #: last cadence sample: an agent that places its tenth block and strikes four
        #: steps later would otherwise be recorded as having struck at 9/10, which is
        #: exactly the number this task exists to measure. `_force` makes that next
        #: query happen immediately instead of at the next multiple of `every`.
        self._pending: list[dict[str, Any]] = []
        self._force = False
        self._start_xz: tuple[float, float] | None = None
        self._warned_shape = False
        self._frames_dir = self.output_dir / "portal_frames"

    # -- lifecycle -------------------------------------------------------------
    def after_reset(self, sim, obs, info):
        self.step = 0
        self._asked = False
        self._pending = []
        self._force = False
        self.trace = portal.PortalTrace(window=self.window)
        self._prev = dict(info)
        here = location(info)
        self._start_xz = (here["x"], here["z"]) if here else None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[portal] probe armed: window={list(self.window)} every={self.every}")
        return obs, info

    def before_step(self, sim, action):
        # `self.step` is the index of the step about to run, since after_step
        # increments. Asking on the step *before* reading keeps the two in phase.
        if self.step % self.every == 0 or self._force:
            action["voxels"] = list(self.window)
            self._asked = True
            self._force = False
        return action

    def after_step(self, sim, obs, reward, terminated, truncated, info):
        self.step += 1
        step = self.step
        try:
            self._observe(step, obs, info)
        except Exception as e:  # noqa: BLE001 - a scoring probe must not kill a run
            logger.warning(f"[portal] probe failed at step {step}: {e}")
        self._asked = False
        self._prev = dict(info)
        return obs, reward, terminated, truncated, info

    def before_close(self, sim):
        self.write()

    # -- the work --------------------------------------------------------------
    def _observe(self, step: int, obs: dict, info: dict) -> None:
        here = location(info)
        # BEFORE the fold, not after: once the agent is in the Nether the voxel answers
        # describe the game's own portal, and PortalTrace.observe refuses them from here
        # on. Checking afterwards would let one Nether sample into the map.
        if self.trace.dimension_step is None and self._start_xz is not None and here:
            if portal.dimension_jump(self._start_xz, (here["x"], here["z"])):
                self.trace.dimension_step = step
                logger.success(f"[portal] dimension change at step {step}; "
                               f"the frame is measured as it stood in the Overworld")
        if here is not None and self._asked and "voxels" in info:
            origin = (math.floor(here["x"]), math.floor(here["y"]), math.floor(here["z"]))
            was_complete = self.trace.first_complete_step
            was_lit = self.trace.first_lit_step
            ok = self.trace.observe(step, origin, info["voxels"])
            if not ok and not self._warned_shape:
                self._warned_shape = True
                logger.error(f"[portal] cannot read info['voxels']: "
                             f"{type(info['voxels']).__name__} "
                             f"{str(info['voxels'])[:200]!r} -- the report will be empty")
            if ok and was_complete is None and self.trace.first_complete_step == step:
                self._snapshot(obs, f"complete_step{step:06d}")
            if ok and was_lit is None and self.trace.first_lit_step == step:
                self._snapshot(obs, f"lit_step{step:06d}")
            if ok:
                self._resolve_pending()

        struck = (_stat(info, "use_item", "flint_and_steel")
                  - _stat(self._prev, "use_item", "flint_and_steel"))
        if struck > 0:
            n = len(self.trace.ignitions) + len(self._pending) + 1
            path = self._snapshot(obs, f"ignition{n:02d}_step{step:06d}")
            self._pending.append({"step": step, "frame": path})
            self._force = True

    def _resolve_pending(self) -> None:
        """Score every strike that has been waiting for a fresh look at the frame."""
        for item in self._pending:
            ig = self.trace.note_ignition(item["step"], item["frame"])
            logger.info(f"[portal] ignition {len(self.trace.ignitions)} at step "
                        f"{item['step']}: frame {ig.fit.get('matched', 0)}/10, "
                        f"blocked={len(ig.fit.get('blocked_interior', []))}, "
                        f"lit={ig.lit}")
        self._pending = []

    def _snapshot(self, obs: dict, name: str) -> str:
        """Save the point-of-view frame. The geometry is only checkable by looking."""
        if not self.snapshots:
            return ""
        image = (obs or {}).get("image")
        if image is None:
            return ""
        try:
            import cv2
            import numpy as np
            self._frames_dir.mkdir(parents=True, exist_ok=True)
            path = self._frames_dir / f"{name}.png"
            arr = np.asarray(image)
            # obs['image'] is RGB; cv2 writes BGR. The green runner encodes without
            # the swap, so its JPEGs come out channel-reversed -- these are for a
            # person (or a vision model) to check obsidian against stone, so they get
            # the right colours.
            cv2.imwrite(str(path), arr[:, :, ::-1] if arr.ndim == 3 else arr)
            return str(path)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[portal] could not save {name}: {e}")
            return ""

    def write(self, obs: dict | None = None) -> Path:
        """Write `portal_report.json`. Safe to call more than once."""
        if obs is not None:
            self._snapshot(obs, f"final_step{self.step:06d}")
        # A strike on the last step of an episode never got its follow-up query; score
        # it from what is known rather than dropping it.
        self._resolve_pending()
        report = self.trace.summary()
        report["steps"] = self.step
        report["every"] = self.every
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "portal_report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        best = report.get("best_frame") or {}
        logger.info(f"[portal] wrote {path}: best frame {best.get('matched', 0)}/10 "
                    f"complete={best.get('complete')} lit={best.get('lit')} "
                    f"placed={report['counts']['obsidian_placed']} "
                    f"mined={report['counts']['obsidian_mined']} "
                    f"ignitions={report['counts']['ignitions']}")
        return path
