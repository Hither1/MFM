"""Stage 27: the starter reflexes are the tick layer when the runner's guards are off.

`--skills --own-reflexes --no-harness-reflexes` (2026-09-08): skills.py installs
lava_ahead / fell / hit / starving under mine/reflexes/ and the runner's own guards are
off. On stage 25's platform-and-basin world (the Overworld: no Nether lock, no lava
guard) a raw walk toward the lava must be stopped by `lava_ahead` short of the basin
with its [REFLEX] note, and on a platform with a 6-block edge a raw walk off it must
end with `fell`'s note -- and no harness note (no LAVA AHEAD, no FELL) in either.
"""
from __future__ import annotations

import shutil

from mcu_worldmodel.stages.rig import RAW, Rig, main_guard

X, Y, Z = -3000, 30, -5500        # the basin world, underground (the starter's 1.5% band)
DX, DY, DZ = -3000, 80, -5450     # the drop world
DROP = 6


def stage(rig: Rig) -> None:
    from mcu_worldmodel import skills

    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    # the s25 world: platform at Y, stairs down at Z+7..Z+9, lava basin from Z+10
    rig.fill(X - 5, Y - 12, Z - 5, X + 5, Y + 8, Z + 18, "stone")
    rig.fill(X - 4, Y + 1, Z - 4, X + 4, Y + 7, Z + 17, "air")
    for i, zz in enumerate((Z + 7, Z + 8, Z + 9), start=1):
        rig.fill(X - 4, Y - i + 1, zz, X + 4, Y, zz, "air")
    rig.fill(X - 4, Y - 3, Z + 10, X + 4, Y, Z + 16, "air")
    rig.fill(X - 4, Y - 4, Z + 10, X + 4, Y - 4, Z + 16, "lava")
    for xx in (X - 3, X + 3):
        rig.fill(xx, Y + 5, Z - 3, xx, Y + 5, Z + 16, "glowstone")
    # the s24 world: platform A at DY, platform B six lower beyond its south edge
    rig.fill(DX - 4, DY - 12, DZ - 4, DX + 4, DY, DZ + 4, "stone")
    rig.fill(DX - 4, DY + 1, DZ - 4, DX + 4, DY + 8, DZ + 4, "air")
    rig.fill(DX - 4, DY - DROP - 3, DZ + 5, DX + 4, DY - DROP, DZ + 13, "stone")
    rig.fill(DX - 4, DY - DROP + 1, DZ + 5, DX + 4, DY + 8, DZ + 13, "air")
    for xx in (DX - 3, DX + 3):
        rig.fill(xx, DY + 5, DZ - 3, xx, DY + 5, DZ + 12, "glowstone")

    a = rig.agent
    a.own, a.own_reflexes, a.reflexes, a.skills = True, True, False, True
    a.memory.own = True
    written = skills.write_skills(a.memory.root)
    rd = a.memory.root / "mine" / "reflexes"
    rd.mkdir(parents=True, exist_ok=True)
    for fn in skills.STARTER_REFLEXES:                  # what the model does in its first turn
        shutil.copy(a.memory.root / "skills" / "reflexes" / "scripts" / fn, rd / fn)
    rig.check("the skill package (four reflex examples included) was written, the four copied",
              len(written) == 13 and (rd / "lava_ahead.py").exists(), written)

    # the drop first (a burn from the basin would paint flames into the next frames)
    rig.tp(DX + 0.5, DY + 1, DZ + 0.5, yaw=0, pitch=0)
    rig.clear()
    rig.idle(12)
    y0 = rig.pos()["y"]
    r2 = rig.run([RAW(60, forward=1), RAW(4, jump=1)], label="a raw walk off a 6-block edge, guards off",
                 max_ticks=120)
    p2 = rig.pos()
    fell = [n for n in r2["notes"] if n.startswith("[REFLEX fell]")]
    rig.check("the avatar landed on B, six blocks lower", abs(p2["y"] - (y0 - DROP)) < 0.6, (y0, p2))
    rig.check("one [REFLEX fell] note, the plan dropped",
              len(fell) == 1 and "fell" in fell[0] and "dropped the rest of your plan" in fell[0]
              and r2["ticks"] < 64, r2["notes"])
    rig.check("no harness FELL note", not any(n.startswith("FELL") for n in r2["notes"]), r2["notes"])

    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=15)
    rig.idle(12)
    z0 = rig.pos()["z"]
    r1 = rig.run([RAW(120, forward=1)], label="a raw walk toward the basin, guards off",
                 max_ticks=160)
    p1 = rig.pos()
    lava = [n for n in r1["notes"] if n.startswith("[REFLEX lava_ahead]")]
    rig.check("lava_ahead stopped the walk short of the basin (z < Z+10, on the stairs or above)",
              p1["z"] < Z + 9.8 and p1["y"] >= Y - 2.5 and r1["ticks"] < 120, (z0, p1, r1["ticks"]))
    rig.check("one [REFLEX lava_ahead] note with the share and the step back",
              len(lava) == 1 and "of the lower view during raw" in lava[0]
              and "running the reflex's own actions" in lava[0], r1["notes"])
    rig.check("no harness note (LAVA AHEAD / NETHER) -- the guards are off",
              not any(n.startswith(("LAVA AHEAD", "NETHER")) for n in r1["notes"]), r1["notes"])
    rig.frame("s27_lava_stop")
    rig.check("stats: two fires, no failures",
              a.cursor_stats.get("own_reflex_fires") == 2 and not a.cursor_stats.get("own_reflex_failures"),
              dict(a.cursor_stats))


if __name__ == "__main__":
    main_guard(stage)
