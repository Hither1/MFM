"""Stage 20: a melee mob down the avatar's own shaft.

og8_mfm (2026-09-07, gpt-6-astra): dig_down to y 11, a torch going up on the shaft
wall, and a zombie fell down the shaft into the cell -- 4.5 hp (hard) every 20 ticks.
The bunker reflex dug two blocks with it aboard and capped them both in; dead at step
2603 with a diamond sword in the inventory, 11 milestones and the kit lost. Here: a
1x1 shaft the runner digs itself (the walked column the grid records), difficulty
hard, a zombie WITH AI dropped from a chamber over the shaft mouth. A: a diamond
sword in the hotbar -- the first hit must go straight to the fightback (no bunker at
a shaft bottom with a sword), and the zombie must die with the avatar alive. B:
pickaxes only (og8's hotbar) -- the bunker arms, then gives way the moment its swings
hit the mob instead of the floor; the outcome is recorded, not asserted.

Measured 2026-09-07 (five runs): the blind fightback at the shove's yaw with quarter
turns landed 0-1 swings in 80 ticks (the two are pushed to opposite CORNERS of the
cell: 45 degrees off every quarter), and `forward` into the wall auto-jumped the eye
over the mob's head. Aimed at the cell's centre from where the push left the avatar,
no forward: A kills it in 3 swings, 20 -> 8.8 hp; B (iron pickaxe) kills it, 20 -> 2.
"""
from __future__ import annotations

from mcu_worldmodel.stages.rig import P, Rig, hotbar_of, main_guard

X, Y, Z = -3000, 16, -5560       # the shaft floor; the avatar digs from Y + 4 down to Y


def _round(rig: Rig, label: str, bx: int, bz: int, kit: list[tuple[str, int]],
           expect_alive: bool) -> None:
    y0 = Y + 4
    rig.cmd("/kill @e[type=minecraft:zombie]")
    rig.fill(bx - 4, Y - 5, bz - 4, bx + 4, Y + 12, bz + 4, "stone")
    rig.fill(bx, y0, bz, bx, Y + 8, bz, "air")                      # the shaft mouth, 5 high
    rig.fill(bx - 1, Y + 9, bz - 1, bx + 1, Y + 10, bz + 1, "air")  # the chamber over it
    rig.tp(bx + 0.5, y0, bz + 0.5, yaw=0, pitch=0)
    rig.clear()
    for item, n in kit:
        rig.give(item, n)
    rig.cmd("/effect give @a minecraft:instant_health 1 3", settle=6)
    rig.idle(10)
    pick = hotbar_of(rig, "iron_pickaxe") or hotbar_of(rig, "diamond_pickaxe") or 2
    r = rig.run([P("equip_hotbar", slot=pick), P("dig_down", n=160, until_y=Y)],
                label=f"{label}: dig_down to y {Y}", max_ticks=400)
    p = rig.pos()
    rig.check(f"{label}: the runner dug its own shaft down to y {Y}",
              p is not None and abs(p["y"] - Y) < 0.2, (p, r["notes"][-1:]))
    col = sorted(c for c in rig.agent.grid.walked if c[0] == bx and c[2] == bz)
    rig.check(f"{label}: the grid holds the walked column over the floor cell",
              rig.agent._in_shaft((bx, Y, bz)), col)
    rig.cmd("/effect give @a minecraft:instant_health 1 3", settle=6)
    rig.idle(4)
    hp0 = float(rig.info.get("health", 0.0))
    cs0 = dict(rig.agent.cursor_stats)
    s0 = rig.stats()
    n0 = len(rig.notes)
    rig.codex.push([P("watch", n=600)])
    for _ in range(6):                       # the plan is running (a standing head)
        rig._step(rig.agent.next_action(rig.info))
    rig.summon("zombie", bx + 0.5, Y + 9.0, bz + 0.5, noai=False)
    hits: list[int] = []
    kinds: list[tuple[str, int, float]] = []
    ticks, hp_min, hp = 0, hp0, hp0
    while ticks < 700:
        hp_before = float(rig.info.get("health", 0.0))
        rig._step(rig.agent.next_action(rig.info))
        ticks += 1
        hp = float(rig.info.get("health", 0.0))
        hp_min = min(hp_min, hp)
        if hp < hp_before - 0.5:
            hits.append(ticks)
        if hits and ticks - hits[0] <= 70 and (ticks - hits[0]) % 10 == 5:
            # where the two stand: the command feedback lands in the chat overlay of
            # the next frame (no entity channel in the observation)
            rig.cmd("/data get entity @e[type=minecraft:zombie,distance=..3,limit=1] Pos", settle=1)
            pp = rig.pos() or {}
            rig.frame(f"s20_{label}_t{ticks}_p{pp.get('pitch', 0):.0f}_y{pp.get('yaw', 0):.0f}")
            rig.log(f"   t{ticks:4d} avatar pos=({pp.get('x')}, {pp.get('y')}, {pp.get('z')}) "
                    f"pitch={pp.get('pitch')} yaw={pp.get('yaw')} hp={hp}")
        rf = rig.agent._reflex or {}
        kind = rf.get("kind")
        if kind and (not kinds or kinds[-1][0] != kind):
            kinds.append((kind, ticks, hp))
            pp = rig.pos() or {}
            rig.log(f"   t{ticks:4d} reflex {kind} armed at hp {hp:.1f} "
                    f"pos=({pp.get('x')}, {pp.get('y')}, {pp.get('z')})")
        d = rig.stat_delta(s0, rig.stats())
        if d.get("custom.deaths", 0) >= 1 or d.get("kill_entity.zombie", 0) >= 1:
            break
    rig.idle(6)
    d = rig.stat_delta(s0, rig.stats())
    st = {k: v - cs0.get(k, 0) for k, v in rig.agent.cursor_stats.items()
          if any(w in k for w in ("bunker", "fightback", "hole", "flee"))}
    notes = rig.notes[n0:]
    gaps = [b - a for a, b in zip(hits, hits[1:])]
    rig.log(f"{label}: hits at {hits} (gaps {gaps}), hp {hp0} -> {hp} (min {hp_min}), "
            f"reflexes {kinds}, stats {st}, delta "
            f"{ {k: v for k, v in d.items() if 'damage' in k or 'kill' in k or 'death' in k} }")
    for n in notes[-6:]:
        rig.log(f"   note: {n[:220]}")
    rig.frame(f"s20_{label}_after")
    rig.check(f"{label}: the zombie reached the avatar (1+ hits)", len(hits) >= 1, hits)
    if expect_alive:
        # a sword in the hotbar at a shaft bottom: the fight at the FIRST hit
        rig.check(f"{label}: the first hit went straight to the fightback "
                  f"(shaft_fightbacks +1, no bunker)",
                  st.get("shaft_fightbacks") == 1 and not st.get("bunker_reflexes")
                  and kinds and kinds[0][0] == "fightback", (st, kinds))
        rig.check(f"{label}: the note says it is the shaft bottom and names the sword",
                  any("bottom of your own shaft" in n and "FIGHTING BACK with the "
                      "diamond_sword" in n for n in notes), notes[-4:])
    else:
        # pickaxes only: the bunker arms, then gives way as soon as its swings hit
        # the mob (or at the second hit)
        rig.check(f"{label}: the first hit armed the bunker",
                  any(k[0] == "bunker" for k in kinds), kinds)
        rig.check(f"{label}: the bunker gave way to the fightback (bunker_intercepted "
                  f"or bunker_followed +1, fightback_reflexes +1)",
                  (st.get("bunker_intercepted", 0) + st.get("bunker_followed", 0)) >= 1
                  and st.get("fightback_reflexes", 0) >= 1, (st, kinds))
        rig.check(f"{label}: the note names the weapon the runner fights with",
                  any("FIGHTING BACK with the" in n for n in notes), notes[-4:])
    rig.check(f"{label}: the swings landed (damage_dealt moved)",
              d.get("custom.damage_dealt", 0) > 0, d)
    if expect_alive:
        rig.check(f"{label}: the zombie died and the avatar lived (kill_entity.zombie +1, "
                  f"deaths 0)",
                  d.get("kill_entity.zombie", 0) >= 1 and d.get("custom.deaths", 0) == 0,
                  (d, hp, kinds))
    else:
        rig.log(f"{label}: outcome (not asserted) -- kill {d.get('kill_entity.zombie', 0)} "
                f"deaths {d.get('custom.deaths', 0)} hp {hp}")


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty hard")
    rig.cmd("/time set 6000")
    rig.cmd("/gamemode survival")
    import os
    rounds = os.environ.get("S20_ROUNDS", "AB")
    if "A" in rounds:
        _round(rig, "A", X, Z, [("diamond_sword", 1), ("iron_pickaxe", 1), ("cobblestone", 20)],
               expect_alive=True)
    if "B" in rounds:
        _round(rig, "B", X + 10, Z, [("iron_pickaxe", 1), ("diamond_pickaxe", 1),
                                     ("cobblestone", 20)], expect_alive=False)


if __name__ == "__main__":
    main_guard(stage)
