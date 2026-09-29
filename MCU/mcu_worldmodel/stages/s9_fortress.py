"""Stage 9: the Nether leg of the dragon chain -- a fortress in view, a blaze, an
enderman, and the two crafts that turn their drops into an eye of ender.

On a flat NETHERRACK platform in the Overworld at midday (the colour detectors need
light; the milestones do not care which dimension a blaze or an enderman dies in, and
`/execute in minecraft:the_nether` would put lava, ghasts and darkness between the
macro and the measurement). What is measured:

1. `vision_nether.fortress_in_view`: a nether-brick wall 22 blocks ahead is found, the
   same view with the wall gone is not, and netherrack alone is never a fortress.
2. `explore_nether` stops on the FORTRESS note before reaching the wall, having walked.
3. `explore_nether` tunnels through a 2-thick netherrack wall (blocks broken, distance
   gained) and bridges a sunk lava trench with cobblestone (use_item.cobblestone, no
   drop into the lava -- fire resistance is on for that leg so a failure is a failed
   check, not a dead avatar and a broken stage).
4. `fight_blaze` kills a summoned blaze (NoAI, hovering 1.5 up) and a live one
   (fire resistance on), verified on kill_entity.blaze; the rod is swept, and when the
   50% drop is withheld a rod item is summoned so the sweep itself is still measured
   (the check name says so).
5. `enderman_pit` digs 2 down; `fight(label="enderman")` from the pit kills a NoAI
   enderman at the rim and then a live one, verified on kill_entity.enderman; the
   pearl the same way as the rod.
6. `craft(blaze_powder)` and `craft(ender_eye)` from those drops, verified on
   craft_item.

Every check reads statistics, the inventory or the position; the detector checks read
frames (they are the measurement of a frame detector) and are paired positive/negative.

Result 2026-09-04 (run 6, commit after 7986fcaa): 29/30. The open check is the LIVE
enderman from the pit: a free enderman summoned 1.8 blocks from the rim walked out of
the pit's view (anything past ~3 blocks is below the rim) before the loop's three
still frames, in 3 of 3 attempts on runs 5 and 6 -- a measured limit of the stage's
setup, not of the macro: the NoAI check proves the pit and the fight (7 swings, 40 hp,
the avatar untouched), and in the open the model's own look at the mob (which angers
it and brings it to the rim) is what the pit is dug for.
"""
from __future__ import annotations

import math

import numpy as np

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard, slot_of
from mcu_worldmodel.stages.s4_entities import HELMET, bearing


def stage(rig: Rig) -> None:
    from mcu_worldmodel import vision
    from mcu_worldmodel import vision_nether as VN

    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)

    def home(yaw: float = 0.0, pitch: float = 0.0) -> None:
        rig.tp(x, y, z, yaw=yaw, pitch=pitch)
        rig.idle(6)

    def clear_mobs() -> None:
        rig.cmd("/kill @e[type=!minecraft:player]")
        rig.idle(6)

    def frame_now() -> np.ndarray:
        return np.asarray(rig.info["pov"])

    def platform() -> None:
        rig.platform(x, y - 1, z, r=22, block="netherrack", clear_to=12)

    rig.cmd("/gamerule sendCommandFeedback false")
    rig.cmd("/gamerule doMobSpawning false")
    rig.cmd("/gamerule doDaylightCycle false")
    rig.cmd("/gamerule naturalRegeneration false")
    # Lava starts fires on nearby blocks and fire on netherrack never goes out: run 1
    # of this stage lit the whole platform from the bridge trench, and every later
    # frame was orange. The fire rule is off; the macros under test do not need it.
    rig.cmd("/gamerule doFireTick false")
    rig.cmd("/difficulty easy")
    rig.cmd("/time set 6000")
    rig.cmd("/weather clear")
    platform()
    home(0)
    rig.clear()
    rig.idle(60)

    # == 1. the fortress detector: a nether-brick wall 22 blocks ahead ===============
    rig.frame("s9_netherrack_only")
    f0 = frame_now().copy()
    neg = VN.fortress_in_view(f0)
    frac0 = VN.fortress_fraction(f0)
    print(f"  [detect] netherrack platform only: fortress={neg} frac={frac0}", flush=True)
    rig.check("detector: a netherrack platform under a blue sky is not a fortress",
              neg is None, (neg, frac0))
    # a corridor-sized wall: 9 wide, 6 high, 2 thick, 22 blocks out along +z
    rig.fill(bx - 4, by, bz + 22, bx + 4, by + 5, bz + 23, "nether_bricks")
    rig.idle(10)
    rig.frame("s9_fortress_wall")
    f1 = frame_now().copy()
    pos_hit = VN.fortress_in_view(f1)
    frac1 = VN.fortress_fraction(f1)
    print(f"  [detect] nether-brick wall 22 out: fortress={pos_hit} frac={frac1}", flush=True)
    rig.check("detector: a nether-brick wall 22 blocks ahead is a fortress in view",
              pos_hit is not None, (pos_hit, frac1))
    rig.check("detector: the mass is centred on the heading (offset within 12 degrees)",
              pos_hit is not None and abs(pos_hit[1]) <= 12.0, pos_hit)
    # the same wall seen 40 degrees off the heading: found, with the offset saying where
    home(-40)
    rig.idle(10)
    f2 = frame_now().copy()
    side = VN.fortress_in_view(f2)
    print(f"  [detect] wall 40 degrees right of the heading: {side}", flush=True)
    rig.check("detector: the wall 40 degrees off the heading is found with a rightward "
              "offset (yaw -40 means the wall lies at +40 relative)",
              side is not None and side[1] > 15.0, side)
    home(0)

    # == 2. explore_nether stops on the fortress before reaching it ===================
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 16)
    rig.idle(6)
    p0 = rig.pos()
    r = rig.run([P("explore_nether", axis="z", sign=1, length=40)],
                label="explore_nether toward the wall", max_ticks=600)
    p1 = rig.pos()
    walked = p1["z"] - p0["z"]
    rig.check("explore_nether: stopped with the FORTRESS note",
              any("FORTRESS IN VIEW" in n for n in r["notes"]), r["notes"])
    rig.check("explore_nether: it stopped short of the wall, not against it (walked "
              "under 20 of the 22 blocks)", 0.0 <= walked < 20.0, (p0, p1))
    rig.check("explore_nether: the note carries the bearing (yaw)",
              any("bearing yaw" in n for n in r["notes"]), r["notes"])
    rig.check("explore_nether: the stop counted in cursor_stats.fortress_seen",
              rig.agent.cursor_stats.get("fortress_seen", 0) >= 1, rig.agent.cursor_stats)

    # == 3a. tunnelling through a netherrack wall =====================================
    rig.fill(bx - 4, by, bz + 22, bx + 4, by + 5, bz + 23, "air")     # the wall goes
    home(0)
    rig.idle(6)
    # a 2-thick, 4-high netherrack wall 3 blocks ahead, 7 wide
    rig.fill(bx - 3, by, bz + 3, bx + 3, by + 3, bz + 4, "netherrack")
    rig.idle(6)
    rig.frame("s9_before_tunnel")
    s0 = rig.stats()
    p0 = rig.pos()
    r = rig.run([P("explore_nether", axis="z", sign=1, length=12)],
                label="explore_nether through a wall", max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    p1 = rig.pos()
    rig.frame("s9_after_tunnel")
    print(f"  [tunnel] stat delta {d}, z {p0['z']:.1f} -> {p1['z']:.1f}", flush=True)
    rig.check("explore_nether: tunnelled through the wall (mine_block.netherrack >= 2)",
              d.get("mine_block.netherrack", 0) >= 2, (d, r["notes"]))
    rig.check("explore_nether: came out the other side (z gained >= 8 of 12)",
              p1["z"] - p0["z"] >= 8.0, (p0, p1, r["notes"]))
    rig.check("explore_nether: the note reports blocks broken and the walk",
              any("explore_nether(z+)" in n and "broke" in n for n in r["notes"]),
              r["notes"])

    # == 3b. bridging a sunk lava trench ================================================
    rig.fill(bx - 3, by, bz + 3, bx + 3, by + 3, bz + 4, "air")
    platform()
    home(0)
    rig.clear()
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 16)
    # a trench 4 wide across the path, 4 blocks ahead, lava one level below the floor
    rig.fill(bx - 6, by - 1, bz + 4, bx + 6, by - 1, bz + 7, "air")
    rig.fill(bx - 6, by - 2, bz + 4, bx + 6, by - 2, bz + 7, "lava")
    rig.cmd("/effect give @a minecraft:fire_resistance 600 1")
    rig.idle(10)
    rig.frame("s9_before_bridge")
    print(f"  [bridge] lava fraction at the start: "
          f"{vision.lava_fraction(frame_now()):.3f}", flush=True)
    s0 = rig.stats()
    p0 = rig.pos()
    r = rig.run([P("explore_nether", axis="z", sign=1, length=14)],
                label="explore_nether over lava", max_ticks=900)
    d = rig.stat_delta(s0, rig.stats())
    p1 = rig.pos()
    rig.frame("s9_after_bridge")
    print(f"  [bridge] stat delta {d}, pos {p0} -> {p1}", flush=True)
    rig.check("explore_nether: bridged the trench (use_item.cobblestone >= 3) "
              "[fire resistance on for this leg]",
              d.get("use_item.cobblestone", 0) >= 3, (d, r["notes"]))
    rig.check("explore_nether: stayed at floor level (never dropped into the trench)",
              p1["y"] >= p0["y"] - 0.5, (p0, p1, r["notes"]))
    rig.check("explore_nether: reached the far side (z gained >= 8)",
              p1["z"] - p0["z"] >= 8.0, (p0, p1, r["notes"]))
    rig.check("explore_nether: the bridging was announced in a note",
              any("laying" in n for n in r["notes"]), r["notes"])
    # Fire resistance STAYS on from here: an avatar that touched the lava keeps
    # burning after the effect is cleared (run 2: 20 -> 12 hp during the next step,
    # and the flames at the bottom of the view were real moving blobs for the fight).
    rig.cmd("/effect give @a minecraft:fire_resistance 3000 1")
    rig.fill(bx - 6, by - 2, bz + 4, bx + 6, by - 1, bz + 7, "netherrack")

    # == 4. a blaze: the detector, then fight_blaze ====================================
    platform()
    clear_mobs()
    home(0)
    rig.clear()
    rig.give("diamond_sword", 1)
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    mx, mz = bearing(x, z, 0.0, 3.5)
    rig.summon("blaze", mx, y + 1.5, mz, noai=True)
    rig.idle(20)
    rig.frame("s9_blaze")
    fb = frame_now().copy()
    hint = VN.blaze_hint(fb)
    plain = vision.entity_hint(fb, want="blaze")
    print(f"  [detect] blaze_hint={hint} entity_hint(blaze)={plain}", flush=True)
    rig.check("detector: blaze_hint finds the hovering blaze near the crosshair",
              hint is not None and abs(hint[1] - 320) <= 120 and abs(hint[2] - 180) <= 120,
              hint)
    # lava in view is NOT a blaze: a 3x3 lava pool sunk beside the platform, no mob
    clear_mobs()
    rig.fill(bx - 1, by - 1, bz + 3, bx + 1, by - 1, bz + 5, "air")
    rig.fill(bx - 1, by - 2, bz + 3, bx + 1, by - 2, bz + 5, "lava")
    home(0, pitch=25)
    rig.idle(20)
    rig.frame("s9_lava_not_blaze")
    fl = frame_now().copy()
    lava_hint = VN.blaze_hint(fl)
    lava_plain = vision.entity_hint(fl, want="blaze")
    print(f"  [detect] lava pool: blaze_hint={lava_hint} entity_hint(blaze)={lava_plain} "
          f"lava_fraction={vision.lava_fraction(fl):.3f}", flush=True)
    rig.check("detector: a lava pool in view is not a blaze to blaze_hint",
              lava_hint is None, (lava_hint, lava_plain))
    rig.fill(bx - 1, by - 2, bz + 3, bx + 1, by - 1, bz + 5, "netherrack")
    home(0)
    rig.summon("blaze", mx, y + 1.5, mz, noai=True)
    rig.idle(20)
    s0 = rig.stats()
    r = rig.run([P("fight_blaze", ticks=300)], label="fight_blaze (NoAI)", max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s9_after_blaze")
    print(f"  [blaze] stat delta {d}", flush=True)
    rig.check("fight_blaze: kill_entity.blaze +1 (a NoAI blaze hovering 1.5 up, 3.5 out) "
              "[fire resistance on]", d.get("kill_entity.blaze") == 1.0, (d, r["notes"]))
    rig.check("fight_blaze: the note names the kill",
              any("KILLED blaze" in n for n in r["notes"]), r["notes"])
    r = rig.run([RAW(20, forward=1), P("collect_drops", ticks=100)], label="sweep the rod",
                max_ticks=200)
    rod_rng = r["inv"].get("blaze_rod", 0) >= 1
    if not rod_rng:
        p = rig.pos()          # where the avatar IS after the fight, not the spawn
        rig.cmd(f"/summon minecraft:item {p['x']} {p['y'] + 1} {p['z'] + 1.0} "
                f'{{Item:{{id:"minecraft:blaze_rod",Count:1b}}}}')
        rig.idle(6)
        r = rig.run([P("collect_drops", ticks=80)], label="sweep a summoned rod",
                    max_ticks=150)
    rig.check("blaze_rod picked up after the kill"
              + ("" if rod_rng else " (the 50% drop was withheld by RNG; a rod item "
                                    "was summoned to measure the sweep)"),
              r["inv"].get("blaze_rod", 0) >= 1, (r["inv"], r["notes"]))

    # -- a LIVE blaze: it moves and shoots; fire resistance keeps the avatar alive ------
    clear_mobs()
    home(0)
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    rig.summon("blaze", mx, y + 1.0, mz, noai=False)
    rig.idle(20)
    s0 = rig.stats()
    r = rig.run([P("fight_blaze", ticks=400)], label="fight_blaze (live)", max_ticks=600)
    d = rig.stat_delta(s0, rig.stats())
    if d.get("kill_entity.blaze", 0) < 1:
        r2 = rig.run([P("fight_blaze", ticks=400)], label="fight_blaze (live, 2nd call)",
                     max_ticks=600)
        d = rig.stat_delta(s0, rig.stats())
        r["notes"] += r2["notes"]
    rig.frame("s9_after_live_blaze")
    print(f"  [blaze live] stat delta {d}", flush=True)
    rig.check("fight_blaze: a LIVE blaze (moving, shooting) is killed within two calls "
              "[fire resistance on]", d.get("kill_entity.blaze", 0) >= 1, (d, r["notes"]))

    # == 5. an enderman: the pit, then fight from inside ================================
    clear_mobs()
    platform()
    home(0)
    rig.clear()
    rig.give("diamond_sword", 1)
    rig.give("diamond_pickaxe", 1)
    rig.give("cobblestone", 8)
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    rig.idle(6)
    y0 = rig.pos()["y"]
    r = rig.run([P("enderman_pit")], label="enderman_pit", max_ticks=400)
    p_pit = rig.pos()
    rig.frame("s9_pit")
    rig.check("enderman_pit: the avatar stands 2 blocks lower (y -2)",
              p_pit["y"] <= y0 - 1.9, (y0, p_pit, r["notes"]))
    rig.check("enderman_pit: the note says the pit is ready",
              any("2-deep pit" in n for n in r["notes"]), r["notes"])
    # a NoAI enderman two blocks from the rim, ahead
    ex, ez = bearing(x, z, 0.0, 2.0)
    rig.summon("enderman", ex, y, ez, noai=True)
    rig.idle(20)
    rig.frame("s9_enderman_from_pit")
    print(f"  [detect] enderman from the pit: "
          f"{vision.entity_hint(frame_now(), want='enderman')}", flush=True)
    s0 = rig.stats()
    r = rig.run([P("fight", ticks=400, label="enderman", retreat_hp=2)],
                label="fight enderman (NoAI) from the pit", max_ticks=600)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s9_after_enderman")
    print(f"  [enderman] stat delta {d}", flush=True)
    rig.check("fight(enderman) from the pit: kill_entity.enderman +1",
              d.get("kill_entity.enderman") == 1.0, (d, r["notes"]))
    rig.check("fight(enderman): the avatar never left the pit",
              rig.pos()["y"] <= y0 - 1.9, (y0, rig.pos()))
    r = rig.run([P("pillar_up", n=2), RAW(6, forward=0), P("look_abs", pitch=20),
                 RAW(24, forward=1), P("collect_drops", ticks=100)],
                label="climb out and sweep the pearl", max_ticks=400)
    pearl_rng = r["inv"].get("ender_pearl", 0) >= 1
    if not pearl_rng:
        p = rig.pos()
        rig.cmd(f"/summon minecraft:item {p['x']} {p['y'] + 1} {p['z'] + 1.0} "
                f'{{Item:{{id:"minecraft:ender_pearl",Count:1b}}}}')
        rig.idle(6)
        r = rig.run([P("collect_drops", ticks=80)], label="sweep a summoned pearl",
                    max_ticks=150)
    rig.check("ender_pearl picked up after the kill"
              + ("" if pearl_rng else " (the 50% drop was withheld by RNG; a pearl item "
                                      "was summoned to measure the sweep)"),
              r["inv"].get("ender_pearl", 0) >= 1, (r["inv"], r["notes"]))

    # -- a LIVE enderman: aggroed by the look from a fresh pit -------------------------
    clear_mobs()
    platform()
    home(0)
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    rig.idle(6)
    r = rig.run([P("enderman_pit")], label="enderman_pit (2)", max_ticks=400)
    # A free enderman wanders off within a few ticks of spawning, and from the pit
    # anything past ~3 blocks is below the rim (runs 2 and 4: "nothing to fight"). So
    # the mob is summoned 1.8 blocks out and the fight starts on the next tick; an
    # attempt whose mob strolled away before the loop found it is repeated, up to
    # three, and the check is the kill in any of them.
    s0 = rig.stats()
    hp0 = float(rig.info.get("health", 20.0))
    notes: list[str] = []
    attempts = 0
    for attempt in range(3):
        attempts = attempt + 1
        clear_mobs()
        ex, ez = bearing(x, z, 0.0, 1.8)
        rig.summon("enderman", ex, y, ez, noai=False)
        r = rig.run([P("fight", ticks=400, label="enderman", retreat_hp=2)],
                    label=f"fight a live enderman from the pit ({attempts})", max_ticks=700)
        notes += r["notes"]
        d = rig.stat_delta(s0, rig.stats())
        if d.get("kill_entity.enderman", 0) >= 1:
            break
    hp1 = float(rig.info.get("health", 20.0))
    rig.frame("s9_after_live_enderman")
    print(f"  [enderman live] stat delta {d}, health {hp0} -> {hp1}, attempts {attempts}",
          flush=True)
    rig.check(f"fight(enderman) from the pit: a LIVE enderman is killed (attempt "
              f"{attempts} of up to 3; a free one wanders out of the pit's view)",
              d.get("kill_entity.enderman", 0) >= 1, (d, notes))
    rig.check("the pit kept the avatar out of its reach (health lost < 8 over the fight)",
              hp0 - hp1 < 8.0, (hp0, hp1))

    # == 6. blaze powder and the eye of ender from the drops =============================
    # On the flat platform, not on the climb-out pillar: run 4 crafted the powder on
    # top of a 2-block pillar (craft_item +2, the rod gone) and the powder was in no
    # slot afterwards -- with the frame still showing the rod in the cell and an empty
    # output. The same craft on flat ground (s9_probe_craft) landed in hotbar 8.
    platform()
    home(0)
    rig.ensure_closed()
    if rig.inv().get("blaze_rod", 0) < 1:
        rig.give("blaze_rod", 1)
    if rig.inv().get("ender_pearl", 0) < 1:
        rig.give("ender_pearl", 1)
    rig.idle(8)
    s0 = rig.stats()
    # Two plans, and the screen closed and reopened between them: the second craft's
    # ingredient is the first craft's OUTPUT, the inventory observation lags the
    # take-out by ~15 ticks (run 2: "need 1x blaze_powder, have 0"), and the frame's
    # [GRID] reading keeps showing the consumed rod in the cell and a FULL output
    # after the shift-click (probe: craft(ender_eye) refused for "leftovers"), which a
    # fresh screen clears.
    r = rig.run([P("open_inventory"), P("craft", item="blaze_powder"),
                 P("close_inventory")], label="blaze_powder", max_ticks=400)
    rig.idle(16)
    r_sweep = rig.run([P("collect_drops", ticks=60)], label="sweep (diagnostic: a "
                      "product dropped at the close would land here)", max_ticks=120)
    print(f"  [craft] after the powder: inv {rig.inv()}", flush=True)
    r2 = rig.run([P("open_inventory"), P("craft", item="ender_eye"),
                  P("close_inventory")], label="ender_eye", max_ticks=400)
    rig.idle(16)
    d = rig.stat_delta(s0, rig.stats())
    print(f"  [craft] stat delta {d}, inv {rig.inv()}", flush=True)
    rig.check("craft(blaze_powder): craft_item.blaze_powder +1 from the rod, and the "
              "powder is in the inventory",
              d.get("craft_item.blaze_powder", 0) >= 1
              and rig.inv().get("blaze_powder", 0) + d.get("craft_item.ender_eye", 0) >= 1,
              (d, rig.inv(), r["notes"], r_sweep["notes"]))
    rig.check("craft(ender_eye): craft_item.ender_eye +1 from powder + pearl (its own "
              "plan, the screen reopened: the inventory lags a take-out by ~15 ticks "
              "and the [GRID] frame reading keeps the consumed cell)",
              d.get("craft_item.ender_eye", 0) >= 1, (d, rig.inv(), r2["notes"]))

    rig.cmd("/gamerule sendCommandFeedback true")


if __name__ == "__main__":
    main_guard(stage)
