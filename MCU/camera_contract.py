"""What the host's camera field actually does, told to every arm the same way.

`src/prompt.txt` is the benchmark's control reference and both purple agents fold it into
their system prompt. Whether its camera section is true depends on how the host builds the
simulator, and under `MinecraftSim`'s default it is not.

Under `MinecraftSim`'s `agent` default -- which the green agent once used --
every `action_type="env"` camera value round-trips through `CameraHierarchicalMapping`'s
mu-law binning (`CameraConfig(binsize=2, maxval=10, mu=10)`) and only 11 values per axis
survive. Measured against the repo's own transformer: `[0, 90]` arrives as 69.7, `[45, 0]`
as 34.9, and the one-slot GUI move of 4.32 degrees as 3.215. The host prompt's continuous
angles and its "<= 8 degrees" advice were all wrong, and `NOTE` says so.

The green agent now builds the simulator with `action_type="env"`, where `step` passes the
dict straight to the game. Measured against the live simulator on 2026-08-25: yaw exact
from 0.25 through 179 degrees in a single tick, pitch exact to its own +/-90 clamp, 4.32
arriving as 4.3200. The host prompt is now accurate and there is nothing to correct, so
`NOTE` is withheld -- appending it would introduce the error it was written to remove.

The switch is `mcu_worldmodel.camera.QUANTISED`, one source of truth for both arms and for
`camera.split`, so a host that puts the encoder back gets the correction back with it.
"""

#: The only per-axis camera deltas that survive the encoder, in degrees per tick.
REACHABLE = (-10.0, -5.8095, -3.2154, -1.6095, -0.6154,
             0.0, 0.6154, 1.6095, 3.2154, 5.8095, 10.0)

NOTE = """\

---

# Correction to the camera section above (measured against this build)

`camera` is **not** continuous. Every value is snapped by the action encoder
(`CameraConfig(binsize=2, maxval=10, mu_law)`), and per tick, per axis, only these 11
deltas exist:

    0, +-0.615, +-1.610, +-3.215, +-5.810, +-10.0   degrees

Anything else becomes the nearest of those. Consequences that contradict the examples above:

- `[0.0, 90.0]` turns 69.7 degrees, not 90. `[45.0, 0.0]` pitches 34.9, not 45.
- **8 is not a safe hop.** It rounds *up* to 10. The "<= 8 degrees" advice overshoots by 25%.
- A single tick can never turn more than 10 degrees.

**To turn by a total angle, spend several ticks and sum values from that list.** 90 degrees
is nine ticks of 10 and is then exact. 45 degrees is 10,10,10,10,3.215,1.610 (44.8).

**In the inventory GUI**, one 18px slot is 4.32 degrees of cursor motion, which is not in
the list: asked for in one tick it moves 13.4px, a quarter of a slot short, every time.
Compose it as `3.215 + 0.615 + 0.615` = 4.446 degrees = 18.5px, i.e. three ticks per slot.
Two slots is `5.810 + 1.610 + 0.615 + 0.615` = 8.65 degrees = 36.1px.

Position yourself with these sums rather than with a round number, and keep checking the
frame -- the arithmetic gets the cursor to the right neighbourhood, not to the right pixel.
"""


def with_camera_truth(platform_prompt: str) -> str:
    """The host's control reference, corrected only where it is actually wrong.

    Empty in, empty out: an agent that was sent no platform prompt is being run outside the
    benchmark, and inventing a correction to a document it never received would be noise.
    Faithful camera in, unchanged out: the host's own description is right and a correction
    would be the error.
    """
    if not platform_prompt:
        return platform_prompt
    from mcu_worldmodel.camera import QUANTISED
    if not QUANTISED:
        return platform_prompt
    return platform_prompt + NOTE
