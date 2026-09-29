"""Stage 8: the bunker reflex in a two-high tunnel, then against a live skeleton.

Three from-scratch runs died at y 14-28 on 2026-09-03 (kd40z_wm twice, kd41z_lb),
each after the pillar reflex reported "the block did not place": a jump under a
tunnel ceiling gains no height, so nothing goes under the feet. The bunker digs two
blocks straight down and caps the cell the feet started in. Part A triggers it with
instant damage (deterministic, one hit 20 -> 8) and then executes the dig-out the
note recommends; part B shoots arrows at the avatar's back on a skeleton's cadence
while it mines, and asserts the bunker completes alive and that arrows shot straight
down into the hole afterwards do no damage.
"""
from __future__ import annotations

import math

import numpy as np

from mcu_worldmodel import vision

from mcu_worldmodel.stages.rig import P, Rig, main_guard

X, Y, Z = -3000, 16, -5560


def tunnel(rig: Rig, yaw: float) -> None:
    """Fresh stone around, a one-wide two-high tunnel 12 long along +z, the avatar
    two blocks in, facing `yaw`."""
    rig.fill(X - 4, Y - 5, Z - 4, X + 4, Y + 6, Z + 16, "stone")
    rig.fill(X, Y, Z, X, Y + 1, Z + 12, "air")
    rig.tp(X + 0.5, Y, Z + 2.5, yaw=yaw, pitch=0)
    rig.idle(10)


def tunnel_long(rig: Rig) -> None:
    """The same one-wide two-high tunnel, 52 long (Z-40 .. Z+12), the avatar at Z+2.5
    facing +z: room to run the other way (the fight macro's own retreat backs the
    avatar down the tunnel first)."""
    rig.fill(X - 4, Y - 5, Z - 44, X + 4, Y + 6, Z + 16, "stone")
    rig.fill(X, Y, Z - 40, X, Y + 1, Z + 12, "air")
    rig.tp(X + 0.5, Y, Z + 2.5, yaw=0.0, pitch=0)
    rig.idle(10)


def bunker_stats(rig: Rig) -> dict[str, int]:
    return {k: v for k, v in rig.agent.cursor_stats.items() if "bunker" in k}


def tick_until(rig: Rig, cond, max_ticks: int) -> int:
    """Tick the runner (plans from the script, reflexes included) until `cond()`."""
    t = 0
    while t < max_ticks:
        rig._step(rig.agent.next_action(rig.info))
        t += 1
        if cond():
            break
    return t


def until_reflex_done(rig: Rig, max_ticks: int, trace: bool = False) -> int:
    """Tick the runner until the armed reflex has finished (or the budget ends)."""
    t = 0
    while t < max_ticks:
        action = rig.agent.next_action(rig.info)
        rig._step(action)
        t += 1
        if trace:
            rf = rig.agent._reflex or {}
            p = rig.pos() or {}
            keys = {k: v for k, v in action.items()
                    if k in ("attack", "use", "forward", "back", "left", "right", "jump")
                    and v}
            rig.log(f"   t{t:3d} {rf.get('phase', '-'):11s} hp={float(rig.info.get('health', 0)):4.1f} "
                    f"pos=({p.get('x')}, {p.get('y')}, {p.get('z')}) pitch={p.get('pitch')} "
                    f"{keys}")
        if rig.agent._reflex is None and t > 2:
            break
    return t


def stage(rig: Rig) -> None:
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 6000")
    rig.cmd("/gamemode survival")
    rig.clear()
    rig.give("stone_pickaxe", 1)
    rig.give("cobblestone", 20)

    # == A. one 12-damage hit while strip-mining at y 16 =============================
    tunnel(rig, yaw=0.0)
    rig.frame("s8_before")
    hp0 = float(rig.info.get("health", 20.0))
    cs0 = dict(rig.agent.cursor_stats)
    sA = rig.stats()
    rig.codex.push([P("strip_mine", length=40)])
    for _ in range(12):                       # the plan is running (a digging head)
        rig._step(rig.agent.next_action(rig.info))
    rig.cmd("/effect give @a minecraft:instant_damage 1 1")       # amplifier 1 = 12 hp
    hp1 = float(rig.info.get("health", 20.0))
    p_hit = rig.pos() or {}          # the cycle walks up to its face first: the hit cell varies
    hit_at = f"({p_hit.get('x', 0):.0f}, {p_hit.get('y', 0):.0f}, {p_hit.get('z', 0):.0f})"
    armed = rig.agent._reflex is not None and rig.agent._reflex.get("kind") == "bunker"
    rig.check("A: a 12-damage hit at y 16 arms the bunker (health 20 -> 8, plan dropped)",
              armed and hp1 <= 10.0 and not rig.agent.queue,
              f"hp {hp0} -> {hp1} reflex={rig.agent._reflex and rig.agent._reflex.get('kind')} "
              f"queue={len(rig.agent.queue)}")
    t = until_reflex_done(rig, 260)
    rig.idle(8)
    pos = rig.pos() or {}
    st = {k: v - cs0.get(k, 0) for k, v in bunker_stats(rig).items()}
    notes = [n for n in rig.notes if "BUNKER" in n or "bunker" in n]
    rig.frame("s8_capped")
    rig.check("A: the reflex digs two blocks down (y 16 -> 14) within the budget",
              abs(float(pos.get("y", 0)) - 14.0) < 0.15 and t < 260,
              f"pos={pos} ticks={t} stats={st}")
    dA = rig.stat_delta(sA, rig.stats())
    rig.check("A: the cap is placed (bunker_capped +1, use_item.cobblestone +1, "
              "mine_block.stone +2)",
              st.get("bunker_capped") == 1 and dA.get("use_item.cobblestone") == 1.0
              and dA.get("mine_block.stone") == 2.0,
              f"stats={st} delta={dA} notes={notes[-2:]}")
    rig.check("A: the note names the hole and the way out",
              any("BUNKERED you: dug 2 blocks down to y 14 and capped the hole with "
                  f"cobblestone at {hit_at}" in n for n in notes), (hit_at, notes[-2:]))
    # The way out the note recommends, executed as written. (rig.run returns between
    # plan entries -- the queue holds one entry at a time -- so this is ticked by hand.)
    # A verified milestone (here mine_cobblestone, from the cap) ends the plan and hands
    # the turn back, so the climb is its own plan.
    sO = rig.stats()
    n0 = len(rig.notes)
    rig.codex.push([P("look_abs", pitch=-90), P("mine_ahead", n=60)])
    t = tick_until(rig, lambda: rig.stat_delta(sO, rig.stats()).get("mine_block.cobblestone", 0)
                   >= 1.0, 150)
    rig.codex.push([P("pillar_up", n=2)])
    # (a jump alone reaches y 16.2 for a few ticks: wait for the plan to drain too)
    t += tick_until(rig, lambda: not rig.agent.queue
                    and float((rig.pos() or {}).get("y", 0)) >= 15.9, 200)
    rig.idle(8)
    pos = rig.pos() or {}
    dO = rig.stat_delta(sO, rig.stats())
    rig.check("A: look_abs(-90) + mine_ahead + pillar_up(2) breaks the cap and climbs "
              "back to y 16",
              abs(float(pos.get("y", 0)) - 16.0) < 0.15 and dO.get("mine_block.cobblestone") == 1.0,
              f"pos={pos} ticks={t} delta={dO} notes={rig.notes[n0:][-3:]}")
    rig.frame("s8_out")

    # == B. arrows from behind on a skeleton's cadence while the avatar mines ========
    # The field attacker: both mob deaths on 2026-09-03 (kd40z_wm, kd41z_lb) were
    # skeleton arrows in a strip mine. A skeleton with AI summoned in this tunnel fired
    # once in 1,400 ticks (run 2), and a zombie (run 4) followed the avatar INTO the
    # hole -- a melee mob standing on the cap cell blocks the placement and reaches
    # the avatar; that case is the model's to run from, not the bunker's. Summoned
    # arrows at 1.6 blocks/tick every 40 ticks (a skeleton's interval below hard,
    # ~4 damage each) are the deterministic version of the ranged case.
    rig.cmd("/effect clear @a")
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    rig.cmd("/difficulty normal")
    tunnel(rig, yaw=180.0)                   # facing -z: the end wall is one block away
    cs0 = dict(rig.agent.cursor_stats)
    s0 = rig.stats()
    for _ in range(12):                      # served one at a time as each plan drains
        rig.codex.push([P("look_abs", yaw=180), P("mine_ahead", n=120)])

    def shoot() -> None:
        rig.cmd(f"/summon minecraft:arrow {X + 0.5} {Y + 1.2} {Z + 6.5} "
                f"{{Motion:[0.0d,0.0d,-1.6d]}}", settle=1)

    def armed() -> bool:
        return rig.agent._reflex is not None and rig.agent._reflex.get("kind") == "bunker"
    ticks, fired, hp_at_arm, hp_min = 0, 0, None, 20.0
    while ticks < 1400:
        if ticks % 40 == 0:
            shoot()
            fired += 1
        rig._step(rig.agent.next_action(rig.info))
        ticks += 1
        hp = float(rig.info.get("health", 0.0))
        hp_min = min(hp_min, hp)
        if hp_at_arm is None and armed():
            hp_at_arm = hp
            rig.log(f"   bunker armed at tick {ticks}, hp {hp}, after {fired} arrows")
        if hp_at_arm is not None:
            rf = rig.agent._reflex or {}
            pp = rig.pos() or {}
            rig.log(f"   t{ticks:4d} {rf.get('phase', '-'):11s} hp={hp:4.1f} "
                    f"pos=({pp.get('x')}, {pp.get('y')}, {pp.get('z')})")
            if rig.agent._reflex is None:
                break
        if rig.stat_delta(s0, rig.stats()).get("custom.deaths", 0) >= 1:
            break
    d = rig.stat_delta(s0, rig.stats())
    rig.check("B: the arrows arm the bunker before the avatar dies",
              hp_at_arm is not None and hp_at_arm > 0 and d.get("custom.deaths", 0) == 0,
              f"hp_at_arm={hp_at_arm} ticks={ticks} arrows={fired} deaths={d.get('custom.deaths')} "
              f"damage_taken={d.get('custom.damage_taken')}")
    rig.idle(8)
    st = {k: v - cs0.get(k, 0) for k, v in bunker_stats(rig).items()}
    hp_capped = float(rig.info.get("health", 0.0))
    dmg_capped = rig.stat_delta(s0, rig.stats()).get("custom.damage_taken", 0)
    pos = rig.pos() or {}
    rig.frame("s8_arrows_capped")
    rig.check("B: the bunker completes under fire (two down, capped, alive)",
              st.get("bunker_capped") == 1 and hp_capped > 0
              and abs(float(pos.get("y", 0)) - 14.0) < 0.15,
              f"stats={st} hp={hp_capped} hp_min={hp_min} pos={pos} ticks={ticks}")
    # Three arrows straight down into the hole: the cap has to stop them.
    for _ in range(3):
        rig.cmd(f"/summon minecraft:arrow {pos.get('x', X + 0.5)} {Y + 3.5} "
                f"{pos.get('z', Z + 2.5)} {{Motion:[0.0d,-1.6d,0.0d]}}", settle=10)
    rig.idle(60)
    d2 = rig.stat_delta(s0, rig.stats())
    rig.check("B: three arrows shot down into the hole afterwards do no damage (the cap holds)",
              d2.get("custom.damage_taken", 0) == dmg_capped and d2.get("custom.deaths", 0) == 0
              and float(rig.info.get("health", 0.0)) > 0,
              f"damage_taken {dmg_capped} -> {d2.get('custom.damage_taken')} "
              f"deaths={d2.get('custom.deaths')} hp={rig.info.get('health')}")
    rig.cmd("/kill @e[type=minecraft:arrow]")

    # == C. a fight head at critical health: the flee, not the bunker ===============
    # dm26z_lb (2026-09-03, y 18) fought a zombie from 16 hp; at 4 hp the bunker armed
    # and the avatar died inside the dig. With a combat head the attacker is melee by
    # construction: turn around and sprint. (A live zombie here was not repeatable:
    # the fight macro's own retreat backed the avatar to the dead end (run 6), and a
    # slow zombie killed it before the head was a fight (run 7); the target is a NoAI
    # zombie and the damage is instant-damage effects.)
    rig.cmd("/effect clear @a")
    rig.cmd("/effect give @a minecraft:instant_health 1 3")
    rig.idle(5)
    if float(rig.info.get("health", 0.0)) < 19.0:
        rig.cmd("/effect give @a minecraft:instant_health 1 3")
        rig.idle(5)
    rig.cmd("/difficulty normal")
    tunnel_long(rig)
    rig.summon("zombie", X + 0.5, Y, Z + 5.5, noai=True)
    rig.idle(5)
    # Health to 14 first (one instant-damage effect is reliable; two in a row were
    # not, runs 8-9), with no plan queued: the hit's turn reflex is cleared.
    rig.cmd("/effect give @a minecraft:instant_damage 1 0", settle=6)      # 20 -> 14
    rig.agent._reflex = None
    rig.agent.queue.clear()
    hp_mid = float(rig.info.get("health", 0.0))
    cs0 = dict(rig.agent.cursor_stats)
    s0 = rig.stats()
    rig.log(f"C: before the fight plan: hp_mid={hp_mid} hotbar={rig.hotbar() if hasattr(rig, 'hotbar') else '?'} "
            f"notes={[n[:90] for n in rig.notes[-2:]]}")
    rig.codex.script.clear()      # plans the arrow section queued and never served
    rig.codex.push([P("fight", ticks=200, retreat_hp=2, weapon="stone_pickaxe",
                      label="zombie")])
    for k in range(6):
        rig._step(rig.agent.next_action(rig.info))
        h = rig.agent.queue[0][0] if rig.agent.queue else None
        rig.log(f"C tick {k + 1}: hp={rig.info.get('health')} head={h and list(h)[:1]} "
                f"reflex={rig.agent._reflex} q={len(rig.agent.queue)} "
                f"note={rig.notes[-1][:100] if rig.notes else ''}")
    head = rig.agent.queue[0][0] if rig.agent.queue else None
    kept = head is not None and "_fight" in head and rig.agent._reflex is None
    # One arrow from behind at speed 6 (8-12 damage measured): 14 -> 2..6, critical.
    rig.cmd(f"/summon minecraft:arrow {X + 0.5} {Y + 1.2} {Z - 1.5} "
            f"{{Motion:[0.0d,0.0d,6.0d]}}", settle=6)

    def fleeing() -> bool:
        return rig.agent._reflex is not None and rig.agent._reflex.get("kind") == "flee"
    hp_at_arm = float(rig.info.get("health", 0.0))
    p0 = rig.pos() or {}
    rig.check("C: at 14 hp a fight head is running; one arrow to critical arms the FLEE, "
              "not the bunker",
              6.0 < hp_mid < 20.0 and kept
              and fleeing() and hp_at_arm > 0
              and (rig.agent.cursor_stats.get("bunker_reflexes", 0)
                   == cs0.get("bunker_reflexes", 0)),
              f"head={head and list(head)[:1]} hp_mid={hp_mid} kept={kept} "
              f"reflex={rig.agent._reflex and rig.agent._reflex.get('kind')} hp={hp_at_arm}")
    t = until_reflex_done(rig, 120, trace=True)
    rig.idle(4)
    p1 = rig.pos() or {}
    d = rig.stat_delta(s0, rig.stats())
    ran = math.hypot(float(p1.get("x", 0)) - float(p0.get("x", 0)),
                     float(p1.get("z", 0)) - float(p0.get("z", 0)))
    st = {k: v - cs0.get(k, 0) for k, v in rig.agent.cursor_stats.items() if "flee" in k}
    notes = [n for n in rig.notes if "sprinted" in n or "sprint you away" in n]
    rig.frame("s8_fled")
    rig.check("C: the flee turns away from the target and runs 5+ blocks, alive",
              ran >= 5.0 and float(rig.info.get("health", 0.0)) > 0
              and d.get("custom.deaths", 0) == 0 and st.get("flee_reflexes") == 1
              and any("turned you around and sprinted" in n for n in notes),
              f"ran={ran:.1f} from {p0} to {p1} hp={rig.info.get('health')} ticks={t} "
              f"stats={st} notes={notes[-1:]}")
    rig.kill("zombie")
    rig.cmd("/difficulty peaceful")

    # -- D. lava: a hit while lava fills the lower view -> douse with the water bucket
    #       (hotbar) and step back; without a bucket, step back only. Peaceful: the lava
    #       is the only damage. The avatar is teleported INTO a one-cell lava source sunk
    #       in the tunnel floor two blocks ahead of its start (hd5z_wm, 2026-09-04: burned
    #       to death at a pool with a water bucket in hotbar 9 while the runner dug).
    for variant, give_bucket in (("D1 with a water bucket", True), ("D2 without a bucket", False)):
        rig.codex.script.clear()
        tunnel(rig, 0.0)
        rig.fill(X, Y - 1, Z + 4, X, Y - 1, Z + 4, "lava")
        rig.clear()
        if give_bucket:
            rig.give("water_bucket", 1)
        rig.give("cobblestone", 8)
        rig.give("stone_pickaxe", 1)
        # part C leaves the avatar at 1 hp (run 3: the first lava hit killed it outright)
        rig.cmd("/effect give @a minecraft:instant_health 1 5")
        rig.cmd("/effect clear @a")
        rig.idle(10)
        rig.log(f"{variant}: health before the lava {rig.info.get('health')}")
        rig.agent._reflex = None
        rig.agent.queue.clear()
        s0 = rig.stats()
        l0 = rig.agent.cursor_stats.get("lava_reflexes", 0)
        d0 = rig.agent.cursor_stats.get("lava_doused", 0)
        n0 = len(rig.notes)
        rig.tp(X + 0.5, Y - 0.7, Z + 4.5, yaw=0.0, pitch=15)
        t = tick_until(rig, lambda: rig.agent._reflex is not None
                       and rig.agent._reflex.get("kind") == "lava", 80)
        armed = rig.agent._reflex is not None and rig.agent._reflex.get("kind") == "lava"
        rig.check(f"{variant}: the first lava hit arms the lava reflex, not the bunker/turn",
                  armed and rig.agent.cursor_stats.get("lava_reflexes", 0) == l0 + 1,
                  (t, rig.agent._reflex, rig.notes[n0:][-2:]))
        t2 = until_reflex_done(rig, 120, trace=True)
        p = rig.pos() or {}
        d = rig.stat_delta(s0, rig.stats())
        notes = rig.notes[n0:]
        alive = not any("YOU DIED" in n for n in notes) and float(rig.info.get("health", 0)) > 0
        # "back" is relative to the facing at the time, and the first hit's turn reflex
        # may already have spun the avatar round (run 4: it left the cell toward +z)
        moved_back = abs(float(p.get("z", Z + 4.5)) - (Z + 4.5))
        rig.log(f"{variant}: reflex ran {t2} ticks, pos={p}, hp={rig.info.get('health')}, "
                f"delta={ {k: v for k, v in d.items() if 'bucket' in k or 'damage' in k} }")
        rig.check(f"{variant}: the avatar is alive after the escape",
                  alive, (rig.info.get("health"), notes[-2:]))
        if give_bucket:
            rig.check("D1: it stepped out of the doused cell (>= 0.9 blocks along the tunnel, on the floor)",
                      moved_back >= 0.9 and float(p.get("y", 0)) >= Y - 0.2, (p, moved_back))
        else:
            # Lava movement is ~0.02 blocks a tick in this engine (run 1: 0.24 blocks in
            # 17 ticks), so a 1x1 pit is not left in the ticks a life allows without the
            # bucket; the check is that the escape was attempted for its full budget.
            rig.check("D2: the escape kept stepping back for its budget (>= 14 ticks) -- lava is too slow to leave a 1x1 pit without the bucket",
                      t2 >= 14, (t2, p, moved_back))
        if give_bucket:
            rig.check("D1: the water bucket was poured (use_item.water_bucket +1, the empty bucket back) and the note says DOUSED",
                      d.get("use_item.water_bucket") == 1.0 and rig.inv().get("bucket", 0) == 1
                      and rig.agent.cursor_stats.get("lava_doused", 0) == d0 + 1
                      and any("DOUSED you" in n for n in notes), (d, rig.inv(), notes[-2:]))
        else:
            rig.check("D2: the note says no water bucket was in the hotbar",
                      any("had no water bucket" in n for n in notes), notes[-2:])
        rig.frame(f"s8_{variant.split()[0]}")

    # == E. a second hit inside MELEE_CADENCE while the bunker digs -> it digs ON =======
    # hd9z_wm (2026-09-04, y 44): the bunker armed at 8 hp against 4-damage hits every
    # ~25 ticks and died with the hole a block deep. Until 2026-09-06 the second hit
    # ended the bunker and the flee ran; stage s16 (a live zombie behind, the avatar at
    # its mining face) showed the flee runs into the face and the avatar dies at 5 hp,
    # while the corpus had 0 completed bunkers in 4. Now the first hit of 3+ arms the
    # bunker (BUNKER_HP 17.5) and further hits do not abandon it: it digs on and caps.
    rig.cmd("/difficulty peaceful")
    rig.cmd("/effect clear @a")
    rig.cmd("/effect give @a minecraft:instant_health 1 5", settle=6)
    rig.clear()
    rig.give("stone_pickaxe", 1)
    rig.give("cobblestone", 20)
    # D2 left the avatar BURNING (lava fire outlasts the teleport and the heal), and a
    # hit with flames over the lower view is the lava reflex by design (s8 run of
    # 2026-09-04 07:05: E's first hit armed "lava"): a dip in water puts it out.
    rig.fill(X, Y, Z + 2, X, Y, Z + 2, "water")
    rig.tp(X + 0.5, Y, Z + 2.5, yaw=0.0, pitch=0)
    rig.idle(8)
    tunnel_long(rig)
    rig.agent._reflex = None
    rig.agent.queue.clear()
    csE = dict(rig.agent.cursor_stats)
    rig.codex.script.clear()      # a stale fight plan at the head would make the hit a combat hit
    rig.codex.push([P("strip_mine", length=40)])
    for _ in range(12):
        rig._step(rig.agent.next_action(rig.info))
    # A FIRST hit: D2's lava damage was under 120 ticks ago, and a repeat hit on a moving
    # head (strip_mine's walk) keeps the plan running by design. The effect's damage lands
    # ~4 ticks after the command (probe_melee 2026-09-04): tick the runner until it reacts.
    rig.agent._last_hit_step = -1000
    rig.cmd("/effect give @a minecraft:instant_damage 1 0", settle=0)       # 20 -> 14
    t1 = tick_until(rig, lambda: rig.agent._reflex is not None, 12)
    hp1 = float(rig.info.get("health", 0.0))
    fr = rig.info.get("pov")
    rig.log(f"E: first hit reacted after {t1} ticks: hp={hp1} reflex={rig.agent._reflex} "
            f"lava={vision.lava_fraction(np.asarray(fr)) if fr is not None else '?'} "
            f"fire={vision.fire_fraction(np.asarray(fr)) if fr is not None else '?'}")
    k1 = rig.agent._reflex.get("kind") if rig.agent._reflex else None
    rig.check("E: one 6-damage hit to 14 hp on a mining head arms the bunker (BUNKER_HP 17.5)",
              k1 == "bunker" and hp1 <= 14.5,
              f"hp={hp1} reflex={k1} stats={ {k: v - csE.get(k, 0) for k, v in bunker_stats(rig).items()} }")
    for _ in range(16):
        rig._step(rig.agent.next_action(rig.info))
    pE0 = rig.pos() or {}
    rig.cmd("/effect give @a minecraft:instant_damage 1 0", settle=0)       # 14 -> 8
    for _ in range(8):
        rig._step(rig.agent.next_action(rig.info))
    hp2 = float(rig.info.get("health", 0.0))
    k2 = rig.agent._reflex.get("kind") if rig.agent._reflex else None
    rig.log(f"E: after the second hit: hp={hp2} reflex={rig.agent._reflex}")
    rig.check("E: the second hit ~24 ticks later does NOT end the bunker (it digs on)",
              k2 == "bunker" and hp2 > 0
              and not any("kept hitting into the dig" in n for n in rig.notes[-6:]),
              f"hp={hp2} reflex={k2} notes={[n[:80] for n in rig.notes[-2:]]}")
    tE = until_reflex_done(rig, 170, trace=True)
    rig.idle(4)
    pE1 = rig.pos() or {}
    stE = {k: v - csE.get(k, 0) for k, v in bunker_stats(rig).items()}
    rig.check("E: the bunker completes under the hits (two down, capped) and the avatar is alive",
              stE.get("bunker_capped", 0) >= 1 and float(rig.info.get("health", 0.0)) > 0
              and float(pE1.get("y", 99)) <= float(pE0.get("y", 0)) - 1.5,
              f"stats={stE} from {pE0} to {pE1} hp={rig.info.get('health')} ticks={tE}")
    rig.frame("s8_melee_bunker")

    # == F. the melee cadence with a sword in the hotbar: fight back, and hit ==========
    # hd21z_wm (2026-09-04, y 25): fled up its own one-wide staircase at 12 hp with a
    # diamond sword in hand, hit every 26 ticks for 8 blocks, dead at 4. A NoAI zombie
    # two blocks ahead (+z), the avatar turned to face -z: the first effect (20 -> 14,
    # no cobblestone, so no bunker) leaves the turn; the second, 20 ticks on, arms the
    # FIGHTBACK, which turns the avatar back to +z and swings the sword at the zombie.
    rig.cmd("/difficulty peaceful")
    rig.cmd("/effect clear @a")
    rig.cmd("/effect give @a minecraft:instant_health 1 5", settle=6)
    rig.clear()
    rig.give("stone_pickaxe", 1)
    rig.give("diamond_sword", 1)
    rig.fill(X, Y, Z + 2, X, Y, Z + 2, "water")
    rig.tp(X + 0.5, Y, Z + 2.5, yaw=0.0, pitch=0)
    rig.idle(8)
    tunnel_long(rig)
    rig.cmd("/difficulty normal")
    rig.summon("zombie", X + 0.5, Y, Z + 4.5, noai=True)
    rig.idle(5)
    rig.agent._reflex = None
    rig.agent.queue.clear()
    rig.codex.script.clear()
    rig.agent._last_hit_step = -1000
    csF = dict(rig.agent.cursor_stats)
    sF = rig.stats()
    rig.cmd("/effect give @a minecraft:instant_damage 1 0", settle=0)       # 20 -> 14
    tF1 = tick_until(rig, lambda: rig.agent._reflex is not None, 12)
    k1 = rig.agent._reflex.get("kind") if rig.agent._reflex else None
    rig.log(f"F: first hit reacted after {tF1} ticks: hp={rig.info.get('health')} reflex={rig.agent._reflex}")
    rig.check("F: the first hit (no cobblestone) is the turn, not a bunker or a fight",
              rig.agent._reflex is not None and k1 is None, str(rig.agent._reflex))
    rig.agent._reflex = None
    rig.tp(X + 0.5, Y, Z + 2.5, yaw=180.0, pitch=0)             # facing -z, the zombie behind
    rig.idle(12)
    rig.cmd("/effect give @a minecraft:instant_damage 1 0", settle=0)       # 14 -> 8
    tF2 = tick_until(rig, lambda: rig.agent._reflex is not None
                     and rig.agent._reflex.get("kind") == "fightback", 12)
    notesF = [n for n in rig.notes if "FIGHTING BACK" in n]
    rig.log(f"F: second hit reacted after {tF2} ticks: hp={rig.info.get('health')} reflex={rig.agent._reflex}")
    rig.check("F: the second hit ~20 ticks later arms the FIGHTBACK with the diamond_sword",
              rig.agent._reflex is not None and rig.agent._reflex.get("kind") == "fightback"
              and rig.agent._reflex.get("item") == "diamond_sword"
              and any("diamond_sword" in n for n in notesF),
              f"reflex={rig.agent._reflex} notes={notesF[-1:]}")
    tF = until_reflex_done(rig, 160, trace=True)
    rig.idle(4)
    dF = rig.stat_delta(sF, rig.stats())
    stF = {k: v - csF.get(k, 0) for k, v in rig.agent.cursor_stats.items() if "fightback" in k}
    notesF2 = [n for n in rig.notes if "fought back with the diamond_sword" in n]
    rig.log(f"F: reflex ran {tF} ticks, delta={ {k: v for k, v in dF.items() if 'damage' in k or 'zombie' in k or 'sword' in k} } stats={stF}")
    rig.check("F: the swings killed the zombie (kill_entity.zombie +1; 5 hp a charged swing) and the avatar is alive",
              dF.get("kill_entity.zombie", 0) >= 1.0 and dF.get("custom.damage_dealt", 0) >= 150
              and float(rig.info.get("health", 0)) > 0
              and stF.get("fightback_damage", 0) >= 15, f"delta={dF} stats={stF}")
    rig.check("F: the note reports the fight (ticks, damage dealt, health) and what to do next",
              bool(notesF2) and "dealt" in notesF2[-1] and "wall the tunnel behind you" in notesF2[-1],
              notesF2[-1:])
    rig.frame("s8_fightback")
    rig.ensure_closed()


if __name__ == "__main__":
    main_guard(stage)
