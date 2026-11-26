#!/usr/bin/env python3
"""Moments a nether_search life stood within RANGE blocks of a mapped fortress AND faced it
(instrument; nothing reaches an agent). Pose = the [STATE] line after each logged action
(logs.txt `Action N | Step S` header: S is the END step of that action). Facing: the bearing
to the nearest point of the fortress's brick box lies within HALF_FOV of the yaw (+x is
-sin yaw, +z is cos yaw). Prints step, pose, distance, angle off-centre; frames are
hires/<step:07d>.jpg (BGR)."""
import math, re, sys
from pathlib import Path
FORTS = {"NE": (-338, -126, -1040, -813), "SW": (-694, -503, -342, -151)}
RANGE, HALF_FOV = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0, 40.0

def nearest(x, z, b):
    return (min(max(x, b[0]), b[1]), min(max(z, b[2]), b[3]))

t = (Path(sys.argv[1]) / "episode_001/memory/logs.txt").read_text(errors="replace")
step = None
hits = []
for line in t.splitlines():
    m = re.match(r"Action \d+ \| Step (\d+)", line)
    if m:
        step = int(m.group(1)); continue
    m = re.match(r"\[STATE\] pos=\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\) pitch=(-?[\d.]+) yaw=(-?[\d.]+)", line)
    if not m or step is None:
        continue
    x, y, z, pitch, yaw = map(float, m.groups())
    for name, b in FORTS.items():
        nx, nz = nearest(x, z, b)
        d = math.hypot(nx - x, nz - z)
        if d > RANGE:
            continue
        # aim at the box's nearest point and its centre; take the better
        best = 999
        for tx, tz in ((nx, nz), ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2)):
            want = math.degrees(math.atan2(-(tx - x), tz - z))      # yaw facing (tx, tz)
            off = abs((yaw - want + 180) % 360 - 180)
            best = min(best, off)
        hits.append((step, name, round(d), round(best), round(x), round(y), round(z), round(pitch), round(yaw)))
near = [h for h in hits]
facing = [h for h in hits if h[3] <= HALF_FOV and -35 <= h[7] <= 25]
print(f"{Path(sys.argv[1]).name}: {len(near)} poses within {RANGE:.0f} of a fortress box, {len(facing)} facing it (pitch -35..25)")
for h in sorted(facing, key=lambda h: h[2])[:12]:
    print("  step %d %s dist %d off %d deg pos (%d,%d,%d) pitch %d yaw %d" % h)
