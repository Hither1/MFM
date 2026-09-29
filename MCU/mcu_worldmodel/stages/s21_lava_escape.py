"""Stage 21: in the pool, out along the trail.

Three of the four deaths of 2026-09-07 were at the lava pool the run had just found:
og10 (first hit at 15/20 with 14% lava in the frame -> the bunker dug INTO the pool),
og11 (first hit -> the 180-degree turn, then the runner's back-step walked it deeper;
the model's own pour had emptied the bucket), og8 (fell through the cell it had mined
the obsidian out of). Lava takes 4.0 every 10 ticks: 50 ticks from full health.

Here: a lit stone room at y 11, a 3x3 pool flush with the floor; the avatar walks 6
blocks up to the rim (the trail on the map), then is put INTO the pool's near cell
facing AWAY from the trail (the og11 case). A: water bucket + cobblestone in the hotbar
-- the first hit must arm the lava escape (no bunker, no turn), pour, and walk back
onto the trail alive. B: no bucket -- the same walk back, the outcome recorded.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 11, -5560


def _room(rig: Rig, bx: int, bz: int) -> None:
    rig.fill(bx - 10, Y - 6, bz - 8, bx + 10, Y + 6, bz + 8, "stone")
    rig.fill(bx - 8, Y, bz - 6, bx + 8, Y + 1, bz + 6, "air")
    for xx in range(bx - 7, bx + 8, 3):
        rig.fill(xx, Y + 2, bz - 5, xx, Y + 2, bz + 5, "glowstone")
    rig.fill(bx + 3, Y - 1, bz - 1, bx + 5, Y - 1, bz + 1, "lava")     # flush with the floor


def _round(rig: Rig, label: str, bx: int, bz: int, kit: list[tuple[str, int]],
           expect_alive: bool) -> None:
    _room(rig, bx, bz)
    rig.tp(bx - 4.5, Y, bz + 0.5, yaw=-90, pitch=0)          # facing +x, the pool ahead
    rig.clear()
    for item, n in kit:
        rig.give(item, n)
    rig.cmd("/effect give @a minecraft:instant_health 1 3", settle=6)
    rig.idle(10)
    r = rig.run([P("go_to", x=bx + 1.5, z=bz + 0.5, within=0.6, n=160)],
                label=f"{label}: walk to the rim", max_ticks=240)
    p = rig.pos()
    # (the lava guard stops the walk a block or two short of the rim: that is the trail)
    rig.check(f"{label}: the trail reached the pool's side (x >= bx - 0.5)",
              p is not None and p["x"] >= bx - 0.5, p)
    home = rig.agent._lava_home({"x": bx + 3.5, "y": Y - 1.0, "z": bz + 0.5,
                                 "pitch": 0.0, "yaw": -90.0})
    rig.check(f"{label}: the runner knows the way back (_lava_home on the trail)",
              home is not None and bx - 1.0 <= home[0] <= bx + 2.0
              and abs(home[1] - (bz + 0.5)) < 0.1, home)
    hp0 = float(rig.info.get("health", 0.0))
    cs0 = dict(rig.agent.cursor_stats)
    s0 = rig.stats()
    n0 = len(rig.notes)
    rig.codex.push([P("watch", n=400)])
    for _ in range(4):
        rig._step(rig.agent.next_action(rig.info))
    # INTO the pool's near cell, facing away from the trail (+x)
    rig.cmd(f"/tp @p {bx + 3.5} {Y - 1} {bz + 0.5} -90 0", settle=1)
    hits: list[int] = []
    kinds: list[tuple[str, int, float]] = []
    ticks, hp = 0, hp0
    while ticks < 200:
        hp_before = float(rig.info.get("health", 0.0))
        rig._step(rig.agent.next_action(rig.info))
        ticks += 1
        hp = float(rig.info.get("health", 0.0))
        if hp < hp_before - 0.5:
            hits.append(ticks)
        rf = rig.agent._reflex or {}
        kind = rf.get("kind")
        if kind and (not kinds or kinds[-1][0] != kind):
            kinds.append((kind, ticks, hp))
            pp = rig.pos() or {}
            rig.log(f"   t{ticks:4d} reflex {kind} armed at hp {hp:.1f} "
                    f"pos=({pp.get('x')}, {pp.get('y')}, {pp.get('z')}) yaw={pp.get('yaw')}")
        if ticks % 10 == 0:
            pp = rig.pos() or {}
            rig.log(f"   t{ticks:4d} hp={hp:.1f} pos=({pp.get('x')}, {pp.get('y')}, "
                    f"{pp.get('z')}) yaw={pp.get('yaw')} phase={rf.get('phase', '-')}")
        d = rig.stat_delta(s0, rig.stats())
        if d.get("custom.deaths", 0) >= 1:
            break
        if kinds and rig.agent._reflex is None and ticks - kinds[-1][1] > 30 and hits \
                and ticks - hits[-1] > 25:
            break                                   # out and no longer burning
    rig.idle(6)
    d = rig.stat_delta(s0, rig.stats())
    st = {k: v - cs0.get(k, 0) for k, v in rig.agent.cursor_stats.items()
          if any(w in k for w in ("lava", "bunker", "flee", "fightback", "pillar"))}
    notes = rig.notes[n0:]
    p = rig.pos() or {}
    rig.log(f"{label}: hits at {hits}, hp {hp0} -> {hp}, reflexes {kinds}, stats {st}, "
            f"final pos ({p.get('x')}, {p.get('y')}, {p.get('z')}), deaths "
            f"{d.get('custom.deaths', 0)}")
    for n in notes[-4:]:
        rig.log(f"   note: {n[:240]}")
    rig.frame(f"s21_{label}_after")
    rig.check(f"{label}: the pool hurt the avatar", len(hits) >= 1, hits)
    rig.check(f"{label}: the first hit armed the lava escape (no bunker, no turn)",
              kinds and kinds[0][0] == "lava" and st.get("lava_reflexes") == 1
              and not st.get("bunker_reflexes"), (kinds, st))
    if expect_alive:
        rig.check(f"{label}: the water was poured (lava_doused +1)",
                  st.get("lava_doused") == 1, st)
    rig.check(f"{label}: the avatar is back on the trail side, out of the pool "
              f"(x <= bx + 2.6, y >= {Y - 0.2})",
              p and p["x"] <= bx + 2.6 and p["y"] >= Y - 0.2, p)
    rig.check(f"{label}: the note names the way back",
              any("back toward the ground you came from" in n for n in notes), notes[-3:])
    if expect_alive:
        rig.check(f"{label}: alive with 6+ health", d.get("custom.deaths", 0) == 0 and hp >= 6.0,
                  (hp, d.get("custom.deaths", 0)))
    else:
        rig.log(f"{label}: outcome (not asserted) -- deaths {d.get('custom.deaths', 0)} hp {hp}")


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 1000")
    rig.cmd("/gamemode survival")
    _round(rig, "A", X, Z, [("water_bucket", 1), ("cobblestone", 20), ("iron_pickaxe", 1)],
           expect_alive=True)
    _round(rig, "B", X, Z + 20, [("cobblestone", 20), ("iron_pickaxe", 1)], expect_alive=False)


if __name__ == "__main__":
    main_guard(stage)
