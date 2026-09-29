"""Stage 10: the eye of ender, the End portal, the End, end stone, a crystal, the dragon.

From prepared states on the platform and in the End (the rig's commands): throw_eye
reports a bearing and fetches the eye (two throws from the same spot agree); a ring of 12
empty end_portal_frame blocks -> fill_end_portal puts an eye in every frame (each verified
on the eye count; the 12th activates the portal, read back through the inventory:
`/execute if block <pit> minecraft:end_portal run give @a stick`), enter_end walks in and
the coordinates jump to the spawn platform; mine_end_stone digs end_stone; a summoned
end crystal is shot with the bow and vanishes (read back the same way with `if entity`);
a summoned dragon takes damage from attack_dragon, and -- with a strength effect standing
in for the 30-odd hits a real kill takes -- kill_entity.ender_dragon registers.
"""
from __future__ import annotations

import math

from mcu_worldmodel.stages.rig import SPAWN, P, Rig, main_guard, hotbar_of


def sticks(rig: Rig) -> int:
    return rig.inv().get("stick", 0)


def probe_block(rig: Rig, x: int, y: int, z: int, block: str) -> bool:
    """True when the block at (x, y, z) is `block` -- read back through the inventory."""
    before = sticks(rig)
    rig.cmd(f"/execute if block {x} {y} {z} minecraft:{block} run give @a minecraft:stick 1",
            settle=6)
    return sticks(rig) > before


def probe_entity(rig: Rig, kind: str, within: float | None = None) -> bool:
    """True when an entity of `kind` exists (within `within` blocks of the avatar) --
    the End has its own ten crystals and its own dragon in loaded chunks, so the
    stage's summoned ones are told apart by distance."""
    before = sticks(rig)
    sel = f"@e[type=minecraft:{kind}" + (f",distance=..{within:g}" if within else "") + "]"
    rig.cmd(f"/execute if entity {sel} run give @a minecraft:stick 1", settle=6)
    return sticks(rig) > before


def frame_ring(cx: int, cy: int, cz: int) -> list[tuple[int, int, int, str]]:
    out = []
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if max(abs(dx), abs(dz)) != 2 or (abs(dx) == 2 and abs(dz) == 2):
                continue
            if abs(dx) > abs(dz):
                facing = "east" if dx < 0 else "west"      # the frame faces the pit
            else:
                facing = "south" if dz < 0 else "north"
            out.append((cx + dx, cy, cz + dz, facing))
    return out


def stage(rig: Rig) -> None:
    x, y, z = SPAWN
    bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
    rig.cmd("/difficulty peaceful")
    rig.cmd("/time set 6000")
    rig.cmd("/weather clear")
    rig.platform(x, y - 1, z, r=16, block="stone", clear_to=14)
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    rig.idle(10)

    # -- throw_eye: two throws from the same spot must agree on the bearing -------------
    rig.give("ender_eye", 8)
    rig.idle(6)
    bearings = []
    for k in range(2):
        rig.tp(x, y, z, yaw=0, pitch=0)
        rig.idle(6)
        eyes0 = rig.inv().get("ender_eye", 0)
        r = rig.run([P("throw_eye")], label=f"throw_eye ({k + 1})", max_ticks=520)
        note = next((n for n in r["notes"] if "flew toward yaw" in n), "")
        m = None
        if note:
            import re
            mm = re.search(r"toward yaw (-?\d+)", note)
            m = float(mm.group(1)) if mm else None
        bearings.append(m)
        rig.check(f"throw_eye ({k + 1}): the eye left the hand and a bearing was reported",
                  m is not None and rig.inv().get("ender_eye", 0) <= eyes0, (r["inv"], r["notes"]))
        rig.frame(f"s10_eye{k + 1}")
        rig.idle(140)      # the eye entity is gone by tick 60; no eye item ever drops (probe_eye2/4)
        before = sticks(rig)
        rig.cmd("/execute if entity @e[type=minecraft:item,nbt={Item:{id:\"minecraft:ender_eye\"}}] "
                "run give @a minecraft:stick 1", settle=6)
        dropped = sticks(rig) > before
        rig.check(f"throw_eye ({k + 1}): the throw consumed the eye (no eye item drops in this engine)",
                  rig.inv().get("ender_eye", 0) == eyes0 - 1 and not dropped, rig.inv())
    if all(b is not None for b in bearings):
        d = abs((bearings[0] - bearings[1] + 180.0) % 360.0 - 180.0)
        rig.check("throw_eye: the two throws agree on the bearing (within 15 degrees)",
                  d <= 15.0, bearings)
    else:
        rig.check("throw_eye: the two throws agree on the bearing (within 15 degrees)",
                  False, bearings)
    rig.log(f"eyes now {rig.inv().get('ender_eye')}")

    # -- travel_bearing: 30 blocks toward yaw 90 on the platform ------------------------
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.idle(6)
    r = rig.run([P("travel_bearing", yaw=90, blocks=12)], label="travel_bearing", max_ticks=300)
    p = rig.pos()
    rig.check("travel_bearing: walked ~12 blocks toward yaw 90 (-x) and said so",
              p is not None and abs((x - p["x"]) - 12) <= 3 and abs(p["z"] - z) <= 3
              and any("blocks covered" in n for n in r["notes"]), (p, r["notes"]))

    # -- fill_end_portal: a 12-frame ring sunk into the platform, 6 blocks ahead ----------
    rig.tp(x, y, z, yaw=0, pitch=0)
    rig.clear()
    cx, cy, cz = bx, by - 1, bz + 7
    for fx, fy, fz, facing in frame_ring(cx, cy, cz):
        rig.cmd(f"/setblock {fx} {fy} {fz} minecraft:end_portal_frame[eye=false,facing={facing}]",
                settle=1)
    rig.fill(cx - 1, cy, cz - 1, cx + 1, cy, cz + 1, "stone")
    ring = frame_ring(cx, cy, cz)
    # three frames already hold an eye: the macro must SKIP them (a click on a filled
    # frame throws the eye away) and fill the other nine
    for fx, fy, fz, facing in ring[:3]:
        rig.cmd(f"/setblock {fx} {fy} {fz} minecraft:end_portal_frame[eye=true,facing={facing}]",
                settle=1)
    rig.give("ender_eye", 9)
    rig.give("cobblestone", 16)
    rig.idle(10)
    rig.frame("s10_ring")
    s0 = rig.stats()
    notes_all = []
    for k in range(1, 4):
        r = rig.run([P("fill_end_portal", x=cx, y=cy, z=cz)], label=f"fill_end_portal ({k})",
                    max_ticks=1500)
        notes_all += r["notes"]
        if k == 1:
            rig.frame("s10_ring_mid")
        if rig.inv().get("ender_eye", 0) == 0 or any("every frame" in n for n in r["notes"]):
            break
    d = rig.stat_delta(s0, rig.stats())
    eyes_left = rig.inv().get("ender_eye", 0)
    filled = [probe_block(rig, fx, fy, fz, "end_portal_frame[eye=true]") for fx, fy, fz, _ in ring]
    rig.check("fill_end_portal: every one of the 12 frames holds an eye afterwards",
              all(filled), (filled, eyes_left, d, notes_all[-3:]))
    rig.check("fill_end_portal: the three pre-filled frames were skipped, nine eyes used",
              eyes_left == 0 and d.get("use_item.ender_eye", 0) == 9.0
              and any("already" in n for n in notes_all), (eyes_left, d, notes_all[-3:]))
    rig.frame("s10_ring_full")
    active = probe_block(rig, cx, cy, cz, "end_portal")
    rig.check("fill_end_portal: the pit holds the End portal block (activated by the last eye)",
              active, (d, notes_all[-2:]))
    # a further call must say every frame has been visited
    r4 = rig.run([P("fill_end_portal", x=cx, y=cy, z=cz)], label="fill_end_portal (again)",
                 max_ticks=100)
    rig.check("fill_end_portal: a further call reports every frame visited",
              any("visited" in n or "every frame" in n for n in r4["notes"]), r4["notes"])
    if not active:
        # so the End half of the stage still runs: the game's own activation is the
        # check above; here the portal blocks are set by hand
        rig.fill(cx - 1, cy, cz - 1, cx + 1, cy, cz + 1, "end_portal")
        rig.idle(6)
        rig.log("portal NOT activated by the macro -- set by command for the End checks")

    # -- enter_end: walk in, land on the spawn platform ---------------------------------
    over = rig.pos()
    r = rig.run([P("enter_end", x=cx, y=cy, z=cz)], label="enter_end", max_ticks=400)
    p = rig.pos()
    rig.check("enter_end: the note says THE END and the coordinates jumped to the platform",
              any("THE END" in n for n in r["notes"]) and p is not None
              and math.dist((p["x"], p["z"]), (over["x"], over["z"])) > 40, (over, p, r["notes"]))
    rig.frame("s10_end_arrival")
    end_pos = rig.pos()

    # -- mine_end_stone: a pickaxe on the pale ground toward the island --------------------
    rig.give("diamond_pickaxe", 1)
    rig.idle(6)
    s0 = rig.stats()
    got = False
    for args in ({}, {"pitch": 60}, {"pitch": 15}, {"yaw": (end_pos["yaw"] + 180.0) if end_pos else 0.0}):
        r = rig.run([P("mine_end_stone", **args)], label=f"mine_end_stone {args}", max_ticks=420)
        if rig.inv().get("end_stone", 0) >= 1:
            got = True
            break
    d = rig.stat_delta(s0, rig.stats())
    rig.check("mine_end_stone: end_stone picked up in the End",
              got or d.get("pickup.end_stone", 0) >= 1, (d, rig.inv(), r["notes"]))
    rig.frame("s10_end_stone")

    # -- break_crystal: a crystal on a 3-block obsidian tower, 8 blocks ahead ------------------
    p = rig.pos()
    px, py, pz = math.floor(p["x"]), math.floor(p["y"]), math.floor(p["z"])
    yaw = p["yaw"]
    dx, dz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    tx, tz = px + round(dx * 8), pz + round(dz * 8)
    rig.platform(p["x"], py - 1, p["z"], r=12, block="end_stone", clear_to=16)
    rig.tp(p["x"], py, p["z"], yaw=yaw, pitch=0)
    rig.fill(tx, py, tz, tx, py + 2, tz, "obsidian")
    rig.cmd(f"/summon minecraft:end_crystal {tx + 0.5} {py + 3} {tz + 0.5}", settle=10)
    rig.idle(6)
    rig.frame("s10_crystal")
    rig.check("a crystal stands on the tower (read back with /execute if entity)",
              probe_entity(rig, "end_crystal", within=14))
    rig.give("bow", 1)
    rig.give("arrow", 16)
    rig.idle(6)
    r = rig.run([P("look_abs", pitch=-12, yaw=yaw), P("break_crystal", shots=4)],
                label="break_crystal (bow)", max_ticks=500)
    gone = not probe_entity(rig, "end_crystal", within=14)
    rig.check("break_crystal: the crystal is gone after the bow shots",
              gone, (r["notes"], rig.inv().get("arrow")))
    rig.check("break_crystal: the note says the crystal was destroyed",
              any("DESTROYED" in n for n in r["notes"]), r["notes"])
    rig.frame("s10_crystal_after")

    # -- attack_dragon: a NoAI dragon 7 blocks ahead at head height ---------------------------
    rig.fill(tx, py, tz, tx, py + 2, tz, "air")
    rig.clear()
    rig.give("diamond_sword", 1)
    rig.tp(p["x"], py, p["z"], yaw=yaw, pitch=0)
    rig.idle(6)
    # Its body parts are what take hits; summoned 5 blocks out at ground level the
    # body and legs are within melee reach after a step or two (7 blocks up and out
    # put only a wing in view: five swings at the sky, run 1).
    # A NoAI dragon's body parts never take a hit here (runs 1-2: 11 swings, no
    # use_item.diamond_sword, no damage_dealt -- the part hitboxes are not placed
    # while its AI is off), so the dragon keeps its AI and the cave keeps it close.
    dxx, dzz = p["x"] + dx * 5, p["z"] + dz * 5
    rig.cmd("/effect give @a minecraft:resistance 120 4", settle=4)      # survive its knocks
    # A full-health dragon with its AI: does a swing land at all?
    rig.summon("ender_dragon", dxx, py + 1, dzz, noai=False, extra="DragonPhase:10")
    rig.idle(12)
    rig.frame("s10_dragon")
    rig.check("a dragon is present (read back with /execute if entity)",
              probe_entity(rig, "ender_dragon", within=30))
    s0 = rig.stats()
    r = rig.run([P("attack_dragon", ticks=300)], label="attack_dragon", max_ticks=400)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("attack_dragon: a swing landed on the dragon (damage_dealt / use_item.diamond_sword)",
              d.get("custom.damage_dealt", 0) > 0 or d.get("use_item.diamond_sword", 0) > 0,
              (d, r["notes"]))
    rig.frame("s10_dragon_hit")
    rig.cmd("/kill @e[type=minecraft:ender_dragon,distance=..40]", settle=10)
    rig.idle(230)          # its death animation
    # The kill: a hovering (DragonPhase 10) dragon with one hit point left, so one
    # landed swing is the kill -- the thirty a 200-hp dragon takes are the same swing.
    rig.tp(p["x"], py, p["z"], yaw=yaw, pitch=0)
    rig.cmd("/effect give @a minecraft:resistance 120 4", settle=4)
    rig.summon("ender_dragon", dxx, py + 1, dzz, noai=False, extra="Health:1f,DragonPhase:10")
    rig.idle(12)
    s0 = rig.stats()
    notes = []
    for k in range(2):
        r = rig.run([P("attack_dragon", ticks=300)], label=f"attack_dragon (1 hp, {k + 1})",
                    max_ticks=400)
        notes += r["notes"]
        if any("DEAD" in n for n in r["notes"]):
            break
    rig.idle(40)
    d = rig.stat_delta(s0, rig.stats())
    rig.check("attack_dragon: kill_entity.ender_dragon registered and the note says DEAD",
              d.get("kill_entity.ender_dragon", 0) >= 1 and any("DEAD" in n for n in notes),
              (d, notes))
    rig.frame("s10_dragon_dead")


if __name__ == "__main__":
    main_guard(stage)
