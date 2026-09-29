"""Stage 4: the entity macros against the real engine.

On a flat stone platform with `/difficulty easy`: build a calibration corpus by
summoning each mob the task suite names and measuring both detectors against it,
measure whether a NoAI mob moves at all, then face a zombie summoned 40 degrees off
the facing, kill it and a pig with `fight`, shear a sheep, milk and lead a cow, cast a
fishing rod at a chicken, shoot a skeleton with the bow, block with a shield, and
place, board, drive and leave a boat on a water pool.

Every behaviour check reads statistics, the inventory or the position. The two
detector checks read frames (they ARE the measurement of a frame detector) but are
paired: the same detector must find the mob when it is there and find nothing after
`/kill`, so a detector that answered "yes" to everything would fail.

Zombies burn in daylight, which would kill the fight target before the macro reached
it, so every hostile summoned here wears a leather helmet (that is the vanilla rule,
not a harness trick) and the world stays at midday where the colour classifier works.
"""
from __future__ import annotations

import json
import math

import numpy as np

from mcu_worldmodel.stages.rig import RAW, SPAWN, P, Rig, main_guard, slot_of

#: The mobs the task suite names, with the summon distance the corpus uses. A phantom
#: and a blaze fly, so they are summoted higher; everything else stands on the floor.
CORPUS = [("zombie", 3.0, 0.0), ("zombie", 6.0, 0.0), ("skeleton", 3.0, 0.0),
          ("spider", 3.0, 0.0), ("creeper", 3.0, 0.0), ("enderman", 4.0, 0.0),
          ("pig", 3.0, 0.0), ("pig", 6.0, 0.0), ("cow", 3.0, 0.0),
          ("sheep", 3.0, 0.0), ("chicken", 2.5, 0.0), ("wolf", 3.0, 0.0),
          ("witch", 3.0, 0.0), ("blaze", 4.0, 1.5), ("phantom", 5.0, 2.5)]
#: Hostiles that burn in the sun; a helmet is the vanilla way to stop that.
BURNS = ("zombie", "skeleton", "phantom")
HELMET = 'ArmorItems:[{},{},{},{id:"minecraft:leather_helmet",Count:1b}]'


def bearing(x: float, z: float, yaw: float, dist: float) -> tuple[float, float]:
    """The (x, z) `dist` blocks from (x, z) on absolute heading `yaw` (0 = +z)."""
    r = math.radians(yaw)
    return (x - dist * math.sin(r), z + dist * math.cos(r))


def stage(rig: Rig) -> None:
    from mcu_worldmodel import vision

    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    calib = rig.out / "calib"
    calib.mkdir(parents=True, exist_ok=True)

    def home(yaw: float = 0.0, pitch: float = 0.0) -> None:
        rig.tp(x, y, z, yaw=yaw, pitch=pitch)
        rig.idle(6)

    def clear_mobs() -> None:
        rig.cmd("/kill @e[type=!minecraft:player]")
        rig.idle(6)

    def spawn(mob: str, dist: float, up: float = 0.0, yaw: float = 0.0,
              noai: bool = True) -> tuple[float, float, float]:
        mx, mz = bearing(x, z, yaw, dist)
        extra = HELMET if mob in BURNS else ""
        rig.summon(mob, mx, y + up, mz, noai=noai, extra=extra)
        rig.idle(8)
        return (mx, y + up, mz)

    def frame_now() -> np.ndarray:
        return np.asarray(rig.info["pov"])

    def two_still() -> tuple[np.ndarray, np.ndarray]:
        """Two consecutive frames with nothing pressed -- the pair the motion
        detector is contracted to receive."""
        rig.idle(1)
        a = frame_now().copy()
        rig.idle(1)
        return a, frame_now().copy()

    rig.cmd("/gamerule sendCommandFeedback false")
    rig.cmd("/gamerule doMobSpawning false")
    rig.cmd("/gamerule doDaylightCycle false")
    rig.cmd("/gamerule naturalRegeneration false")
    rig.cmd("/difficulty easy")
    rig.cmd("/time set 6000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=12, block="stone", clear_to=10)
    home(0)
    rig.clear()
    rig.idle(60)                       # let the chat log fade before any frame diffing

    # == 1. detector calibration corpus =======================================
    # Both detectors are thresholds over rendered pixels; the only honest accuracy
    # number is the one this engine produces. Each mob is summoned alone on an empty
    # platform, framed, then killed -- so every frame has exactly one right answer,
    # and the empty-platform frames are the negatives.
    def on_mob(hit) -> bool:
        """The blob sits where the mob was summoned: dead ahead, so near the crosshair.
        This is the number that matters for AIMING -- a blob on the mob with the wrong
        label still points the crosshair at the right thing."""
        return bool(hit) and abs(hit[-5] - 320) <= 90 and abs(hit[-4] - 175) <= 110

    rows: list[dict] = []
    empty_a, empty_b = two_still()
    rig.frame("s4_empty")
    empty_motion = vision.find_moving_blob(empty_a, empty_b)
    # The negative control is the `want=` scan for the mobs this stage then hunts: the
    # OPEN scan over a forest horizon does find something (measured run 1: a 209 px
    # dirt patch labelled "cow"), which is why the macros pass a label.
    empty_want = {m: vision.entity_hint(empty_b, want=m)
                  for m in ("zombie", "pig", "sheep", "cow", "chicken")}
    rig.check("calib: an empty platform is neither motion nor any hunted mob's colour",
              empty_motion is None and not any(empty_want.values()),
              (empty_motion, empty_want))

    for mob, dist, up in CORPUS:
        clear_mobs()
        pos = spawn(mob, dist, up)
        rig.tp(x, y, z, yaw=0.0, pitch=(0.0 if up else (10.0 if dist <= 3.5 else 5.0)))
        rig.idle(20)                   # settle, and let any command chat fade
        a, b = two_still()
        from PIL import Image
        Image.fromarray(b).save(calib / f"{mob}_{dist:.0f}.jpg", quality=88)
        hint = vision.entity_hint(b)
        want = vision.entity_hint(b, want=mob)
        motion = vision.find_moving_blob(a, b)
        rows.append({"mob": mob, "dist": dist, "open_label": (hint or [None])[0],
                     "open_px": (hint[3] if hint else 0), "open_on_mob": on_mob(hint),
                     "want_found": want is not None, "want_on_mob": on_mob(want),
                     "want_px": (want[3] if want else 0),
                     "motion": bool(motion), "motion_px": (motion[2] if motion else 0)})
        print(f"  [calib] {mob:9s} d={dist:.1f}  open={rows[-1]['open_label']!s:9s} "
              f"on_mob={'y' if rows[-1]['open_on_mob'] else 'n'}  "
              f"want={'y' if rows[-1]['want_on_mob'] else 'n'}  "
              f"motion={'y' if motion else 'n'}({rows[-1]['motion_px']})", flush=True)
    clear_mobs()
    rig.idle(20)
    (rig.out / "calib" / "corpus.json").write_text(json.dumps(rows, indent=1))
    n = len(rows)
    open_lab = sum(1 for r in rows if r["open_label"] == r["mob"])
    open_loc = sum(1 for r in rows if r["open_on_mob"])
    want_loc = sum(1 for r in rows if r["want_on_mob"])
    print(f"  [calib] want= on the mob {want_loc}/{n}; open scan label {open_lab}/{n}, "
          f"blob on the mob {open_loc}/{n}; motion on rigid NoAI mobs "
          f"{sum(1 for r in rows if r['motion'])}/{n}", flush=True)
    # A skeleton's bone and a stone floor are the same grey, and a phantom is the same
    # blue-grey as the sky it flies against: colour cannot separate either (measured
    # run 1, both `want=` misses). Those two are motion-only, which is what the live
    # skeleton in the bow step below exercises.
    hard = {"skeleton", "phantom"}
    findable = [r for r in rows if r["mob"] not in hard]
    # Across five runs of this stage the `want=` scan landed on 12 or 13 of the 15
    # (12 or 13 of the 13 findable): a creeper 3 blocks off renders a blob of only
    # ~155 px of its own green and drops under the floor when the light shifts. The
    # check is that floor, not perfection, because a detector built from thresholds
    # over rendered pixels has run-to-run variance and a check that cries wolf on it
    # teaches nothing.
    got = sum(1 for r in findable if r["want_on_mob"])
    rig.check(f"calib: entity_hint(want=<mob>) puts a blob on at least 12 of the "
              f"{len(findable)} mobs whose colour differs from stone and sky "
              f"(this run: {got})", got >= 12,
              [r["mob"] for r in findable if not r["want_on_mob"]])
    # The open scan (no label) is the FALLBACK: three mobs and the stone floor share one
    # neutral-grey band, so its label is right about half the time and its blob is on the
    # mob about three fifths of the time. That is the floor asserted here; the path the
    # macros actually take passes a label, and that is the check above.
    rig.check("calib: the open scan still puts its blob on the mob for 3/5 of the corpus",
              open_loc * 5 >= n * 3, (open_lab, open_loc, n,
                                      [r["open_label"] for r in rows]))

    # -- does a NoAI mob move at all? the reason the colour path exists -----------
    clear_mobs()
    spawn("pig", 3.0)
    rig.idle(30)
    a, b = two_still()
    rigid = vision.find_moving_blob(a, b)
    clear_mobs()
    spawn("pig", 3.0, noai=False)      # the same mob, free to breathe and wander
    rig.idle(30)
    moved = None
    for _ in range(12):
        a, b = two_still()
        moved = vision.find_moving_blob(a, b)
        if moved:
            break
    rig.frame("s4_motion_pig")
    print(f"  [calib] NoAI pig motion={rigid}, live pig motion={moved}", flush=True)
    rig.check("motion: a LIVE mob is found by the frame difference",
              moved is not None, moved)
    # Twice: the first `/kill` makes the pig DROP porkchop, and a dropped item bobs and
    # spins on the ground -- a real 132 px moving blob (measured run 3). That is the
    # detector working, not failing, but it is not the mob, so the drops go too.
    clear_mobs()
    rig.idle(10)
    clear_mobs()
    rig.idle(20)
    a, b = two_still()
    rig.check("motion: with the mob and its drops gone the same detector finds nothing",
              vision.find_moving_blob(a, b) is None, vision.find_moving_blob(a, b))

    # == 2. face_entity: a zombie 3 blocks out, 40 degrees off the facing ==========
    clear_mobs()
    home(0)
    mob_at = spawn("zombie", 3.0, yaw=40.0)
    rig.idle(20)
    rig.frame("s4_before_face")
    r = rig.run([P("face_entity", ticks=80, label="zombie")], label="face_entity",
                max_ticks=200)
    p = rig.pos()
    want_yaw = math.degrees(math.atan2(-(mob_at[0] - p["x"]), mob_at[2] - p["z"]))
    dyaw = abs((p["yaw"] - want_yaw + 180) % 360 - 180)
    rig.frame("s4_after_face")
    rig.check("face_entity: the avatar now points at the zombie's true bearing "
              "(computed from the summon coordinates and the measured position)",
              dyaw <= 10.0, (p["yaw"], want_yaw, dyaw))
    rig.check("face_entity: the note says it centred", any("centred" in n for n in r["notes"]),
              r["notes"])

    # == 3. fight a zombie, then a pig ============================================
    rig.give("diamond_sword", 1)
    rig.idle(6)
    s0 = rig.stats()
    hp0 = float(rig.info.get("health", 20.0))
    r = rig.run([P("fight", ticks=300, label="zombie")], label="fight zombie",
                max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s4_after_fight_zombie")
    rig.check("fight: kill_entity.zombie +1", d.get("kill_entity.zombie") == 1.0, d)
    rig.check("fight: the swings landed (use_item.diamond_sword and damage_dealt moved)",
              d.get("use_item.diamond_sword", 0) >= 1
              and d.get("custom.damage_dealt", 0) > 0, d)
    rig.check("fight: the note names the kill",
              any("KILLED zombie" in n for n in r["notes"]), r["notes"])

    clear_mobs()
    home(0)
    spawn("pig", 3.0, yaw=-25.0)
    rig.idle(20)
    rig.frame("s4_before_fight_pig")
    print(f"  [detect] pig in view before the fight: "
          f"{vision.entity_hint(frame_now(), want='pig')}", flush=True)
    s0 = rig.stats()
    r = rig.run([P("fight", ticks=300, label="pig")], label="fight pig", max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("fight: a pig 25 degrees off the facing is found and killed",
              d.get("kill_entity.pig") == 1.0, (d, r["notes"]))

    # == 4. use_on_entity: shears on a sheep, bucket and lead on a cow ============
    clear_mobs()
    home(0)
    rig.clear()
    rig.give("shears", 1)
    spawn("sheep", 2.5)
    rig.idle(20)
    rig.frame("s4_before_shear")
    print(f"  [detect] sheep in view before the shear: "
          f"{vision.entity_hint(frame_now(), want='sheep')}", flush=True)
    s0 = rig.stats()
    # Shearing drops the wool ON THE GROUND -- it does not appear in the inventory, so
    # the sweep is part of the act (measured: run 4 sheared the sheep and the check
    # read an unchanged inventory while the wool block sat two blocks away).
    # MEASURED, runs 4-6: shearing a sheep moves NOTHING this agent can read -- no
    # use_item.shears, no statistic, no inventory change. The frame showed a bare sheep
    # and a wool block lying where it stood, so the wool is an item entity and the only
    # way into the inventory is to WALK ONTO it. The macro therefore reports a failure
    # it did not have (its note says so), and the plan has to walk in and sweep.
    r = rig.run([P("use_on_entity", item="shears", ticks=200, label="sheep"),
                 RAW(24, forward=1), P("collect_drops", ticks=120)],
                label="shear the sheep", max_ticks=600)
    d = rig.stat_delta(s0, rig.stats())
    wool = sum(v for k, v in r["inv"].items() if k.endswith("wool"))
    rig.frame("s4_shears")
    print(f"  [shear] stat delta {d}", flush=True)
    rig.check("use_on_entity(shears), walk in, collect_drops: wool in the inventory "
              "(the shear itself is invisible to every observation channel)",
              wool >= 1, (d, r["inv"], r["notes"]))

    clear_mobs()
    home(0)
    rig.clear()
    rig.give("bucket", 1)
    rig.give("lead", 1)
    spawn("cow", 2.5)
    rig.idle(20)
    r = rig.run([P("use_on_entity", item="bucket", ticks=80, label="cow")],
                label="milk the cow", max_ticks=200)
    rig.check("use_on_entity(bucket) on a cow: milk_bucket in the inventory",
              r["inv"].get("milk_bucket", 0) >= 1, (r["inv"], r["notes"]))
    r = rig.run([P("use_on_entity", item="lead", ticks=80, label="cow")],
                label="lead the cow", max_ticks=200)
    rig.check("use_on_entity(lead) on a cow: the lead is attached (lead -1)",
              r["inv"].get("lead", 0) == 0, (r["inv"], r["notes"]))

    # -- fishing rod cast at a chicken ------------------------------------------
    clear_mobs()
    home(0)
    rig.clear()
    rig.give("fishing_rod", 1)
    spawn("chicken", 2.5)
    rig.idle(20)
    s0 = rig.stats()
    r = rig.run([P("use_on_entity", item="fishing_rod", ticks=80, label="chicken")],
                label="hook the chicken", max_ticks=200)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("use_on_entity(fishing_rod): the cast registers (use_item.fishing_rod)",
              d.get("use_item.fishing_rod", 0) >= 1, (d, r["notes"]))

    # == 5. shoot_bow at a skeleton 8 blocks out ==================================
    clear_mobs()
    home(0)
    rig.clear()
    rig.give("bow", 1)
    rig.give("arrow", 8)
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    # Resistance 5 = immune. A live skeleton at 6 blocks KILLED the avatar in run 6
    # (custom.deaths +1) before the third arrow left the bow, which measures the
    # skeleton, not shoot_bow. It still shoots, still moves, still has to be found.
    rig.cmd("/effect give @a minecraft:resistance 120 4")
    # WITH AI: a skeleton's bone grey is the same grey as the stone it stands on, so
    # the colour classifier cannot see it at all (measured above). A live one moves,
    # and motion is the detector that finds anything -- this is the step that proves
    # the motion path end to end against the real engine.
    spawn("skeleton", 6.0, noai=False)
    rig.idle(20)
    a, b = two_still()
    print(f"  [detect] skeleton motion before the shots: "
          f"{vision.find_moving_blob(a, b)}", flush=True)
    s0 = rig.stats()
    r = rig.run([P("shoot_bow", shots=3, label="skeleton")], label="shoot_bow",
                max_ticks=500)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s4_bow")
    rig.check("shoot_bow: three arrows left the bow (use_item.bow +3, arrow -3)",
              d.get("use_item.bow", 0) >= 3 and r["inv"].get("arrow", 0) <= 5,
              (d, r["inv"], r["notes"]))
    rig.check("shoot_bow: at least one arrow hit (custom.damage_dealt moved)",
              d.get("custom.damage_dealt", 0) > 0, (d, r["notes"]))
    rig.cmd("/effect clear @a")

    # == 6. block_with_shield against a live zombie ================================
    clear_mobs()
    home(0)
    rig.clear()
    rig.give("shield", 1)
    rig.cmd(f"/effect give @a minecraft:instant_health 1 20")
    spawn("zombie", 1.6, noai=False)
    rig.idle(20)
    # `custom.damage_taken` (tenths of hp) and not the health bar: health regenerates,
    # and run 2 measured a window where the avatar HEALED 8 hp while standing open.
    s0 = rig.stats()
    r = rig.run([P("face_entity", ticks=40, label="zombie"),
                 P("block_with_shield", ticks=100)], label="block", max_ticks=300)
    blocked = rig.stat_delta(s0, rig.stats()).get("custom.damage_taken", 0.0)
    s0 = rig.stats()
    rig.idle(100)                      # the same exposure with the shield DOWN
    opened = rig.stat_delta(s0, rig.stats()).get("custom.damage_taken", 0.0)
    print(f"  [shield] damage_taken {blocked:.0f} blocking vs {opened:.0f} unblocked "
          f"over the same 100 ticks (tenths of hp)", flush=True)
    rig.check("block_with_shield: the macro ran and reported the health it kept",
              any("shield held up" in n for n in r["notes"]), r["notes"])
    rig.check("block_with_shield: a raised shield takes less damage than standing open "
              "(same zombie, same 100 ticks, custom.damage_taken)",
              blocked < opened, (blocked, opened))

    # == 7. a boat on a water pool: place, board, drive, leave ======================
    clear_mobs()
    rig.clear()
    rig.cmd("/effect clear @a")
    rig.cmd("/effect give @a minecraft:instant_health 1 20")
    # A 7x5 pool two blocks ahead, its surface flush with the platform floor.
    rig.fill(bx - 3, by - 1, bz + 2, bx + 3, by - 1, bz + 8, "water")
    rig.give("oak_boat", 1)
    home(0, pitch=25)
    rig.idle(10)
    s0 = rig.stats()
    # Two blocks out, not three: block reach is 4.5 but ENTITY reach is 3, and a boat
    # placed at exactly 3.0 could not be boarded (stage s4 run 2).
    r = rig.run([P("use_at", x=bx, y=by - 1, z=bz + 2, item="oak_boat", face="above")],
                label="place the boat", max_ticks=200)
    d = rig.stat_delta(s0, rig.stats())
    rig.frame("s4_boat_placed")
    rig.check("the boat is on the water (use_item.oak_boat +1, oak_boat -1)",
              d.get("use_item.oak_boat", 0) >= 1 and r["inv"].get("oak_boat", 0) == 0,
              (d, r["inv"], r["notes"]))
    y_shore = rig.pos()["y"]
    rig.frame("s4_before_board")
    print(f"  [detect] boat in view before boarding: "
          f"{vision.entity_hint(frame_now(), want='boat')} at pitch {rig.pos()['pitch']:.0f}",
          flush=True)
    r = rig.run([P("use_on_entity", item="oak_boat", ticks=200)], label="board the boat",
                max_ticks=400)
    p_in = rig.pos()
    rig.frame("s4_boat_in")
    rig.check("use_on_entity(oak_boat): you are IN the boat (the position dropped into "
              "the hull)", p_in["y"] < y_shore - 0.2, (y_shore, p_in, r["notes"]))
    r = rig.run([P("boat_forward", ticks=40)], label="boat_forward", max_ticks=150)
    p_drive = rig.pos()
    rig.check("boat_forward: the boat moved across the pool",
              math.hypot(p_drive["x"] - p_in["x"], p_drive["z"] - p_in["z"]) > 1.0,
              (p_in, p_drive, r["notes"]))
    r = rig.run([P("leave_boat")], label="leave_boat", max_ticks=100)
    p_out = rig.pos()
    rig.frame("s4_boat_out")
    rig.check("leave_boat: y rose back out of the hull",
              p_out["y"] > p_drive["y"] + 0.15, (p_drive, p_out, r["notes"]))

    rig.cmd("/gamerule sendCommandFeedback true")


if __name__ == "__main__":
    main_guard(stage)
