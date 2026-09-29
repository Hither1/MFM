"""Stage 25: the Nether lock and the descent guard on a slope above lava.

Every Nether visit on record (og9 x2, og12, og13; 2026-09-07) died within 400 steps of
arriving, walking, sprinting or jumping down a slope or off a ledge into the lava sea:
og12's last keys were forward+sprint+jump down a slope from y 36 to 28. Here a lit stone
platform runs into a three-step staircase down to a lava basin. With the runner's
dimension set to the Nether: raw forward+sprint+jump for 60 ticks (og12's keys) must
creep 2-5 blocks on the platform with one NETHER LOCK note (sneak, a quarter of a walk,
no sprint, no moving jump); a raw walk teleported onto the first step (sneak holds an
edge in this world, so the descent is played) must be dropped within a sample with a
NETHER DESCENT note, short of the basin; pillar_up must still rise; and the same keys in
the Overworld must cover 5+ blocks in 30 ticks with no Nether note (the control: the
keys and the slope are real).
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, RAW, Rig, main_guard

X, Y, Z = -3000, 80, -5500      # the platform's floor is at Y; the avatar stands at Y+1


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    # the platform: floor at Y for z Z-4..Z+6; the stairs: Y-1 at Z+7, Y-2 at Z+8, Y-3 at
    # Z+9; the basin: lava surface at Y-4 for z Z+10..Z+16, stone below and around
    rig.fill(X - 5, Y - 12, Z - 5, X + 5, Y + 8, Z + 18, "stone")
    rig.fill(X - 4, Y + 1, Z - 4, X + 4, Y + 7, Z + 17, "air")
    for i, zz in enumerate((Z + 7, Z + 8, Z + 9), start=1):
        rig.fill(X - 4, Y - i + 1, zz, X + 4, Y, zz, "air")
    rig.fill(X - 4, Y - 3, Z + 10, X + 4, Y, Z + 16, "air")
    rig.fill(X - 4, Y - 4, Z + 10, X + 4, Y - 4, Z + 16, "lava")
    for xx in (X - 3, X + 3):
        rig.fill(xx, Y + 5, Z - 3, xx, Y + 5, Z + 16, "glowstone")
    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=15)        # facing +z: the first step 6.5 on
    rig.clear()
    rig.give("cobblestone", 16)
    rig.idle(12)
    p0 = rig.pos()
    y0, z0 = p0["y"], p0["z"]
    a = rig.agent
    a._dimension = "the Nether"
    rig.frame("s25_start")

    r1 = rig.run([RAW(60, forward=1, sprint=1, jump=1)],
                 label="forward+sprint+jump for 60 ticks, the Nether", max_ticks=120)
    p = rig.pos()
    rig.check("the walk crept 2-5 blocks and stayed on the platform",
              2.0 <= p["z"] - z0 <= 5.0 and abs(p["y"] - y0) < 0.6, (p0, p))
    locks = [n for n in r1["notes"] if n.startswith("NETHER LOCK")]
    rig.check("exactly one NETHER LOCK note, no descent note",
              len(locks) == 1 and not any(n.startswith("NETHER DESCENT") for n in r1["notes"]),
              r1["notes"])
    rig.check("the lock counted the ticks and the dropped jumps",
              a.cursor_stats.get("nether_lock_ticks", 0) >= 50
              and a.cursor_stats.get("nether_lock_jumps", 0) >= 50, dict(a.cursor_stats))

    # The descent guard. Sneaking holds an edge in this world (the debug trace of
    # 2026-09-07 23:0x: 150 ticks of forward+sneak at the platform's edge, 0.29 over it,
    # no fall), so a locked walk never steps down by itself; the descent is played by a
    # teleport onto the first step (one block down, the basin in the lower view) while
    # a raw walk runs, and the guard must drop the plan within its next sample.
    rig.codex.push([RAW(200, forward=1)])
    notes0 = len(rig.notes)
    t_tp = None
    for t in range(80):
        action = a.next_action(rig.info)
        rig._step(action)
        if t == 20:
            rig.tp(X + 0.5, Y, Z + 7.5, yaw=0, pitch=15)      # onto the first step
            t_tp = t
        if t_tp is not None and not a.queue:
            break
    ticks_after = (t - t_tp) if t_tp is not None else None
    rig.idle(8)
    p2 = rig.pos()
    notes2 = rig.notes[notes0:]
    desc = [n for n in notes2 if n.startswith("NETHER DESCENT")]
    rig.check("the walk was dropped within 8 ticks of the step down, short of the basin",
              ticks_after is not None and ticks_after <= 8 and not a.queue
              and 0.9 <= y0 - p2["y"] <= 1.6 and p2["z"] < Z + 9.5, (p0, p2, ticks_after))
    rig.check("one NETHER DESCENT note naming the entry, the drop and the lava share",
              len(desc) == 1 and "(raw) walked you 1 block(s) DOWN" in desc[0]
              and "% of the lower view" in desc[0], notes2)
    rig.check("the descent was counted", a.cursor_stats.get("nether_descents") == 1,
              dict(a.cursor_stats))
    rig.frame("s25_dropped")

    r3 = rig.run([P("pillar_up", n=1)], label="pillar_up(1) under the lock", max_ticks=240)
    p3 = rig.pos()
    rig.check("pillar_up still rises one block (a vertical jump keeps its jump)",
              p3["y"] >= p2["y"] + 0.9, (p2, p3, r3["notes"]))

    rig.tp(X + 0.5, Y + 1, Z + 0.5, yaw=0, pitch=15)
    rig.idle(8)
    a._dimension = "the Overworld"
    r4 = rig.run([RAW(30, forward=1, sprint=1, jump=1)],
                 label="the same keys in the Overworld for 30 ticks (control)", max_ticks=80)
    p4 = rig.pos()
    rig.check("the control covers 5+ blocks in 30 ticks", p4["z"] - z0 >= 5.0, (p0, p4))
    rig.check("no Nether note in the Overworld",
              not any(n.startswith("NETHER") for n in r4["notes"]), r4["notes"])


if __name__ == "__main__":
    main_guard(stage)
