"""The camera deltas `MinecraftSim` can actually deliver, and how to hit a target with them.

An `action_type="env"` action's `camera` field does not reach the game as written. The
green agent converts it with `env_action_to_agent_action`, and `MinecraftSim.step` converts
it back, so every delta round-trips through `CameraHierarchicalMapping`'s mu-law binning
(`CameraConfig(binsize=2, maxval=10, mu=10)`). That bins 11 values per axis and **nothing
else is reachable**:

    {0, +-0.615, +-1.610, +-3.215, +-5.810, +-10.0}  degrees per tick

Two consequences, both measured against the repo's own transformer rather than reasoned
about, and both of which were silently wrong before this module existed:

  * `8.0` does not clip to 10 -- it *rounds up* to 10. Every "split into <=8-degree hops"
    helper was overshooting by 25%: `look(0, 90)` delivered 69.7 and `look(0, 180)`
    delivered 230.
  * `4.32` -- the one-slot cursor move that `gui.PX_PER_DEGREE` implies -- delivers
    `3.215`, i.e. 13.4 px against an 18 px slot. Each GUI move landed a quarter-slot short
    while `CursorPath` recorded it as exact.

So a *total* angle is composed from the reachable set instead of divided into equal parts:
`4.32` becomes `3.215 + 0.615 + 0.615 = 4.446` (0.5 px of slot error) rather than one hop
that lands 4.6 px short.

This is an environment-interface correction, not a policy: it makes the agent's stated
intent survive the encoder. What it cannot do is aim -- that is still the agent's job.
"""
from __future__ import annotations

import os

from loguru import logger

#: Fallback, used only if minestudio cannot be imported. Measured against
#: `CameraConfig()` defaults; `reachable()` recomputes it so a config change is followed.
_FALLBACK = (-10.0, -5.8095, -3.2154, -1.6095, -0.6154,
             0.0, 0.6154, 1.6095, 3.2154, 5.8095, 10.0)

_CACHE: tuple[float, ...] | None = None


def reachable() -> tuple[float, ...]:
    """The sorted set of per-tick camera deltas that survive the round trip.

    Derived by decoding every bin rather than assumed, so it tracks `CameraConfig` if the
    benchmark ever changes `n_camera_bins` or the quantisation scheme.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        import numpy as np
        from minestudio.simulator.entry import CameraConfig
        from minestudio.utils.vpt_lib.actions import ActionTransformer
        from minestudio.utils.vpt_lib.action_mapping import CameraHierarchicalMapping

        cc = CameraConfig()
        mapper = CameraHierarchicalMapping(n_camera_bins=cc.n_camera_bins)
        tf = ActionTransformer(**cc.action_transformer_kwargs)
        # One batch, not one call per probe: `env2policy` reads `camera.shape[0]` as the
        # batch size, so the whole sweep costs a single conversion.
        probe = np.arange(-12.0, 12.0001, 0.05, dtype=np.float32)
        batch: dict = {"camera": np.stack([probe, np.zeros_like(probe)], axis=1)}
        out = tf.policy2env(mapper.to_factored(mapper.from_factored(tf.env2policy(batch))))
        _CACHE = tuple(sorted({round(float(v), 4) for v in out["camera"][:, 0]}))
    except Exception as exc:  # a missing simulator must not break offline use
        logger.warning(f"[camera] could not derive the bin set ({exc}); using the measured fallback")
        _CACHE = _FALLBACK
    return _CACHE


def snap(delta: float) -> float:
    """The reachable delta nearest `delta`. What the encoder would have produced anyway."""
    return min(reachable(), key=lambda v: abs(v - delta))


# Whether the encoder is in the path at all. The green agent used to build MinecraftSim
# in its `agent` default, which is what this module exists to survive. It now builds it
# with `action_type="env"`, where `step` passes the camera dict straight to the game and
# a single tick delivers the angle as written -- measured against the live simulator:
# yaw exact from 0.25 to 179 degrees, pitch exact to its own +/-90 clamp, 4.32 arriving
# as 4.3200 rather than 3.2154.
#
# Composing against a bin set the game no longer applies is not merely redundant, it is
# worse than doing nothing: one slot becomes three ticks summing to 4.446 instead of one
# tick of exactly 4.32. So the split collapses unless something puts the encoder back.
QUANTISED = os.environ.get("MCU_CAMERA_QUANTISED", "").strip().lower() in ("1", "true", "yes")


def deliverable(delta: float) -> bool:
    """Will the simulator apply this delta as written?

    Under `QUANTISED` only the bin set survives. Otherwise the field is Box(-180, 180)
    and reaches the game untouched -- measured on the live simulator, yaw exact from
    0.25 through 179 degrees in one tick. Pitch has a further limit that is the game's,
    not the encoder's: it clamps to +/-90, so a large request is applied up to the clamp
    rather than binned, which `CursorPath` handles by tracking where the cursor actually
    ended up.
    """
    if QUANTISED:
        return round(delta, 4) in set(reachable())
    return -180.0 <= delta <= 180.0


def split(total: float, max_ticks: int = 64) -> list[float]:
    """Per-tick deltas summing to `total`: one tick when the camera is faithful, and
    otherwise reachable bins as close to `total` as the set allows.

    Greedy largest-first, which is exact for any multiple of 10 and lands inside 0.2 deg
    otherwise. `max_ticks` bounds a pathological request rather than expressing a policy --
    a 180-degree turn is 18 ticks and that is simply what it costs.
    """
    if not total:
        return []
    if not QUANTISED:
        return [float(total)]
    magnitudes = [v for v in reachable() if v > 0]      # ascending
    smallest = magnitudes[0]
    sign = 1.0 if total > 0 else -1.0
    remaining, out = abs(total), []
    while len(out) < max_ticks and remaining > 0:
        step = next((v for v in reversed(magnitudes) if v <= remaining + 1e-9), None)
        if step is None:
            # Nothing fits. Overshooting by one smallest bin beats stopping short only
            # when it actually reduces the error.
            if abs(remaining - smallest) < remaining:
                out.append(sign * smallest)
            break
        out.append(sign * step)
        remaining -= step
    if len(out) >= max_ticks:
        logger.warning(f"[camera] {total:.1f} deg truncated at {max_ticks} ticks "
                       f"({sum(out):.1f} deg delivered)")
    return out


def plan(pitch: float = 0.0, yaw: float = 0.0) -> list[tuple[float, float]]:
    """Per-tick `[pitch, yaw]` pairs for a combined turn, and what they actually deliver.

    Under `QUANTISED` the axes bin independently, so they are composed separately and
    zipped, whichever finishes first padding with zeros. Otherwise both arrive as asked
    and the pair is a single tick.
    """
    ps, ys = split(pitch), split(yaw)
    n = max(len(ps), len(ys))
    ps += [0.0] * (n - len(ps))
    ys += [0.0] * (n - len(ys))
    return list(zip(ps, ys))
