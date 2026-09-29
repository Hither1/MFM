#!/usr/bin/env python
"""Photograph the dragon task's endgame in the live engine.

No arm has reached the last eight milestones of `kill_ender_dragon`, so nothing under
output/ shows what they look like. This stages each of them with server commands and
saves the frames -- same engine, same renderer, the same 640x360 POV the agent is scored
on -- together with the game's own statistics, so a frame is backed by the event that
actually fired rather than by a scene that merely looks right.

The kills are real kills: mobs are summoned with `NoAI` in front of the player and killed
with the sword, so `kill_entity` and the drop's `pickup` are credited the way the scorer
expects. The two crafts go through the inventory GUI via `gui.craft_actions`, which is the
only crafting path this engine has (see craft_env.py).

Run on a compute node under xvfb:
    export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
    xvfb-run -a -s "-screen 0 1024x768x24" .venv/bin/python scripts/dragon_endgame_frames.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MINESTUDIO_DIR", "/tmp/MineStudio")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from loguru import logger  # noqa: E402

from mcu_worldmodel import gui  # noqa: E402
from mcu_worldmodel import procedures as P  # noqa: E402

RENDER = (640, 360)


class Shoot:
    """The sim plus a frame counter, a command channel and a statistics witness."""

    def __init__(self, sim, out: Path):
        self.sim = sim
        self.out = out
        self.frames = out / "frames"
        self.frames.mkdir(parents=True, exist_ok=True)
        self.idx = 0
        self.steps = 0
        self.info: dict = {}
        self.shots: list[dict] = []

    # -- plumbing ---------------------------------------------------------
    def reset(self):
        obs, self.info = self.sim.reset()
        return self.info

    def cmd(self, command: str):
        """A server command, then one tick so its effect is in the next observation."""
        self.sim.env.execute_cmd(command)
        self.tick(1)
        return self.info

    def tick(self, n: int = 1, action=None):
        act = action or P.noop()
        for _ in range(max(1, n)):
            _obs, _r, _term, _trunc, self.info = self.sim.step(dict(act))
            self.steps += 1
        return self.info

    def run(self, actions, tag: str | None = None, every: int = 0):
        """Step a macro. `every` > 0 also saves a frame every N ticks."""
        for i, a in enumerate(actions):
            _obs, _r, _term, _trunc, self.info = self.sim.step(dict(a))
            self.steps += 1
            if every and tag and i % every == 0:
                self.shot(f"{tag}_t{i:03d}", quiet=True)
        return self.info

    # -- output -----------------------------------------------------------
    def shot(self, name: str, note: str = "", quiet: bool = False) -> str | None:
        pov = self.info.get("pov")
        if pov is None:
            logger.warning(f"[shot] no pov in info for {name}")
            return None
        img = cv2.cvtColor(np.asarray(pov, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        path = self.frames / f"{self.idx:03d}_{name}.png"
        cv2.imwrite(str(path), img)
        self.shots.append({"file": path.name, "step": self.steps, "note": note,
                           "pos": pos_of(self.info)})
        if not quiet:
            logger.info(f"[shot] {path.name} step={self.steps} {note}")
        self.idx += 1
        return str(path)

    def witness(self, label: str, **extra):
        """The statistics the scorer reads, at this instant."""
        rec = {"label": label, "step": self.steps, "pos": pos_of(self.info)}
        for group in ("kill_entity", "craft_item", "pickup", "mine_block"):
            g = self.info.get(group) or {}
            rec[group] = {k: as_num(v) for k, v in g.items() if as_num(v)}
        rec["inventory"] = inv_of(self.info)
        rec.update(extra)
        logger.info(f"[witness] {label}: kills={rec['kill_entity']} "
                    f"craft={rec['craft_item']} pickup={rec['pickup']}")
        (self.out / "witness.jsonl").open("a").write(json.dumps(rec) + "\n")
        return rec


def as_num(v) -> float:
    try:
        return float(v.item()) if hasattr(v, "item") else float(v)
    except Exception:
        return 0.0


def pos_of(info: dict) -> dict | None:
    """Through `milestones.location`, so this reads position the same way `look_at` does
    -- the two disagreeing about which key holds x is a silent aiming error."""
    from mcu_worldmodel.milestones import location
    loc = location(info)
    return {k: round(v, 2) for k, v in loc.items()} if loc else None


def inv_of(info: dict) -> dict:
    inv = info.get("inventory") or {}
    out = {}
    for _slot, e in inv.items():
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        if t in ("none", "air", None):
            continue
        out[t] = out.get(t, 0) + int(as_num(e.get("quantity", 0)))
    return out


def has(info: dict, item: str, group: str = "inventory") -> float:
    if group == "inventory":
        return inv_of(info).get(item, 0)
    return as_num((info.get(group) or {}).get(item, 0))


def player_xyz(info: dict) -> tuple[float, float, float]:
    from mcu_worldmodel.milestones import location
    loc = location(info) or {}
    return (loc.get("x", 0.0), loc.get("y", 0.0), loc.get("z", 0.0))


def player_yaw(info: dict) -> float:
    from mcu_worldmodel.milestones import location
    return (location(info) or {}).get("yaw", 0.0)


#: Survival melee reach is 3.0 blocks to the hitbox. The first run summoned its mobs at
#: 3.4 and every swing missed -- the frames looked right and no `kill_entity` ever fired.
MELEE = 2.2

#: Chat lines fade after 200 ticks. A beauty shot taken before that is a picture of the
#: command log, not of the milestone.
CHAT_FADE = 210


def settle_chat(s: "Shoot") -> None:
    s.tick(CHAT_FADE)


def aim_pitch(s: Shoot, pitch: float, tol: float = 2.0, tries: int = 6) -> None:
    """Steer to an absolute pitch closed-loop. `procedures.look_abs` returns a marker the
    agent's runner resolves, not env actions, so it cannot be stepped from here."""
    for _ in range(tries):
        cur = (pos_of(s.info) or {}).get("pitch", 0.0)
        delta = float(pitch) - cur
        if abs(delta) < tol:
            return
        s.run(P.look(pitch=delta))


# -- combat -------------------------------------------------------------------

def swing_at(s: Shoot, x: float, y: float, z: float, swings: int = 12,
             tag: str | None = None) -> None:
    """Aim at a world point and swing with the attack cooldown respected.

    A held `attack` in this action space is a mining hold, not repeated hits: the sword's
    cooldown means a hit lands only when the button goes down again, so each swing is a
    press followed by ticks of nothing.
    """
    acts, why = P.look_at(s.info, x, y, z)
    if why:
        logger.warning(f"[aim] {why}")
    s.run(acts)
    if tag:
        s.shot(f"{tag}_aimed", "crosshair on the target")
    for i in range(swings):
        s.run(P.repeat(P.act(attack=1), 2))
        s.run(P.repeat(P.noop(), 8))
        if tag and i in (0, 2, 5):
            s.shot(f"{tag}_swing{i}", "mid-fight")


def kill_mob(s: Shoot, mob: str, tag: str, dist: float = MELEE, dy: float = 0.9,
             nbt: str = "{NoAI:1b}", attempts: int = 3, aim_dy: float = 1.0) -> bool:
    """Summon `mob` in front of the player, kill it, and confirm via `kill_entity`.

    Summoned at absolute coordinates rather than `~ ~ ~` so the aim can be computed
    instead of guessed, and with NoAI so an enderman does not teleport out of frame and a
    blaze does not drift.
    """
    before = has(s.info, mob, "kill_entity")
    for attempt in range(attempts):
        px, py, pz = player_xyz(s.info)
        yaw = player_yaw(s.info)
        import math
        fx = -math.sin(math.radians(yaw))
        fz = math.cos(math.radians(yaw))
        mx, my, mz = px + fx * dist, py + dy, pz + fz * dist
        s.cmd(f"/summon minecraft:{mob} {mx:.2f} {my:.2f} {mz:.2f} {nbt}")
        s.tick(6)
        s.shot(f"{tag}_spawned", f"{mob} in view, alive")
        swing_at(s, mx, my + aim_dy, mz, swings=14,
                 tag=tag if attempt == 0 else None)
        s.tick(10)
        if has(s.info, mob, "kill_entity") > before:
            s.shot(f"{tag}_killed", f"{mob} dead, drops on the ground")
            return True
        logger.warning(f"[kill] {mob} attempt {attempt + 1} did not register")
    return False


def gather_drops(s: Shoot, item: str, tag: str, tries: int = 3) -> bool:
    """Walk over the drop. Items land at the mob's feet, a step or two ahead."""
    for i in range(tries):
        s.run(P.repeat(P.act(forward=1), 12))
        s.run(P.repeat(P.noop(), 10))
        s.run(P.repeat(P.act(back=1), 8))
        s.run(P.repeat(P.noop(), 10))
        if has(s.info, item) or has(s.info, item, "pickup"):
            s.shot(f"{tag}_picked_up", f"{item} in the inventory")
            return True
    return False


# -- crafting -----------------------------------------------------------------

#: Signed pixels-per-degree for the GUI cursor, measured live by `calibrate_cursor`.
#: gui.PX_PER_DEGREE is the magnitude; the *sign* of each axis is the thing the
#: calibration run in gui_cal.log never settled, and an open-loop craft with a sign
#: wrong moves the cursor away from every slot -- which is exactly what
#: craft_live.log's "did not craft" was.
PPD = {"x": gui.PX_PER_DEGREE, "y": gui.PX_PER_DEGREE}


def empty_slots(info: dict, k: int = 1) -> list[int]:
    """Empty player slots, main rows first. Not `procedures._empty_slots`: that one tests
    for `"air"`, and this engine reports an empty slot as `"none"` -- so it finds none and
    the crafted item stays on the pointer, to be thrown on the floor at close."""
    inv = info.get("inventory") or {}
    out = []
    for sid in list(range(9, 36)) + list(range(0, 9)):
        e = inv.get(sid, inv.get(str(sid)))
        if isinstance(e, dict) and e.get("type") in ("none", "air", None):
            out.append(sid)
            if len(out) >= k:
                break
    return out


def cursor_xy(s: Shoot):
    from mcu_worldmodel import vision
    pov = s.info.get("pov")
    return None if pov is None else vision.find_cursor(np.asarray(pov))


def calibrate_cursor(s: Shoot) -> bool:
    """Measure how a camera delta moves the GUI cursor, from two probe moves.

    Closed-loop from here on: the cursor is *seen* in the frame every tick rather than
    dead-reckoned, so a quantised camera delta or a clamp at the window edge costs a
    correction instead of the whole craft.
    """
    probe = 6.0
    for axis, cam in (("x", dict(yaw=probe)), ("y", dict(pitch=probe))):
        before = cursor_xy(s)
        if before is None:
            logger.error("[cal] cursor not visible; is the inventory open?")
            return False
        s.run(P.look(**cam))
        s.tick(2)
        after = cursor_xy(s)
        if after is None:
            return False
        moved = (after[0] - before[0]) if axis == "x" else (after[1] - before[1])
        if abs(moved) < 2.0:
            logger.error(f"[cal] {axis}: {probe} deg moved the cursor {moved} px")
            return False
        PPD[axis] = moved / probe
        logger.info(f"[cal] {axis}: {PPD[axis]:.2f} px/deg")
    return True


def move_cursor(s: Shoot, container_xy, tol: float = 3.0, tries: int = 14) -> bool:
    """Drive the cursor onto a container coordinate, correcting from the frame."""
    tx, ty = gui.to_screen(container_xy, RENDER)
    for _ in range(tries):
        cur = cursor_xy(s)
        if cur is None:
            return False
        dx, dy = tx - cur[0], ty - cur[1]
        if abs(dx) <= tol and abs(dy) <= tol:
            return True
        s.run(P.look(pitch=max(-30.0, min(30.0, dy / PPD["y"])),
                     yaw=max(-30.0, min(30.0, dx / PPD["x"]))))
        s.tick(1)
    cur = cursor_xy(s)
    return cur is not None and abs(tx - cur[0]) <= 6 and abs(ty - cur[1]) <= 6


def gui_click(s: Shoot, button: str = "attack") -> None:
    s.run(P.repeat(P.act(**{button: 1}), 2))
    s.tick(2)


def craft_2x2(s: Shoot, item: str, tag: str) -> bool:
    """Craft in the survival inventory, closed-loop, and confirm via `craft_item`.

    Same recipe table and slot geometry as `gui.craft_actions`; what differs is that every
    move ends by looking at where the cursor actually is. The output is deposited into an
    empty slot rather than left on the pointer, since closing the screen with a held item
    throws it on the floor.
    """
    before = has(s.info, item, "craft_item")
    ok, why = gui.can_craft(s.info, item)
    if not ok:
        logger.error(f"[craft] {item}: {why}")
        return False
    grid, cells, _ = gui.RECIPES[item]
    if grid != "2x2":
        logger.error(f"[craft] {item} needs a {grid} table, not staged here")
        return False

    s.run(P.open_inventory())
    s.tick(6)
    s.shot(f"{tag}_inventory_open", "survival inventory, ingredients in hand")
    if not calibrate_cursor(s):
        s.run(P.close_inventory())
        return False

    # One source stack at a time: pick it up, right-click one item into each cell it
    # supplies, put the remainder back.
    by_source: dict[int, list[int]] = {}
    remaining = {ing: [[sl, q] for sl, q in gui.find_slots(s.info, ing)]
                 for ing in set(cells.values())}
    for cell, ing in sorted(cells.items()):
        stacks = remaining[ing]
        while stacks and stacks[0][1] <= 0:
            stacks.pop(0)
        if not stacks:
            logger.error(f"[craft] ran out of {ing}")
            s.run(P.close_inventory())
            return False
        stacks[0][1] -= 1
        by_source.setdefault(stacks[0][0], []).append(cell)

    for src, target_cells in by_source.items():
        if not move_cursor(s, gui.centre(gui.slot_topleft(src))):
            logger.warning(f"[craft] could not reach slot {src}")
        gui_click(s)
        for cell in target_cells:
            if move_cursor(s, gui.centre(gui.SURVIVAL_CRAFT_IN[cell])):
                gui_click(s, "use")
        if move_cursor(s, gui.centre(gui.slot_topleft(src))):
            gui_click(s)
    s.shot(f"{tag}_grid_filled", "recipe laid out in the 2x2 grid")

    if not move_cursor(s, gui.centre(gui.SURVIVAL_CRAFT_OUT)):
        logger.warning("[craft] could not reach the output slot")
    s.shot(f"{tag}_output_shown", "the result sitting in the output slot")
    gui_click(s)
    empty = empty_slots(s.info, 1)
    if empty and move_cursor(s, gui.centre(gui.slot_topleft(empty[0]))):
        gui_click(s)
    s.tick(4)
    got = has(s.info, item, "craft_item") > before
    s.shot(f"{tag}_{'crafted' if got else 'failed'}", f"{item}: craft_item={got}")
    s.run(P.close_inventory())
    s.tick(6)
    return got


# -- stages -------------------------------------------------------------------

PREAMBLE = [
    "/gamemode survival @s",
    # Every command echoes into the chat overlay and the overlay is *in the frame*.
    # Off from the start, and `settle_chat` waits out the lines already printed.
    "/gamerule sendCommandFeedback false",
    "/gamerule doImmediateRespawn true",
    # A staged scene, not a survival run: a wandering piglin should not walk into
    # the frame or take the swing meant for the blaze (it did, in the first run).
    "/gamerule doMobSpawning false",
    "/effect give @s minecraft:regeneration 99999 3 true",
    "/gamerule doDaylightCycle false",
    "/gamerule doWeatherCycle false",
    "/gamerule keepInventory true",
    "/gamerule mobGriefing false",
    "/effect give @s minecraft:resistance 99999 4 true",
    "/effect give @s minecraft:fire_resistance 99999 1 true",
    "/effect give @s minecraft:saturation 99999 4 true",
]


def stage_nether(s: Shoot) -> None:
    """Milestones: kill_blaze, blaze_rod. A blaze drops a rod only to a player kill, and
    only about half the time, so this kills several."""
    logger.info("=== stage: the Nether ===")
    s.cmd("/execute in minecraft:the_nether run teleport @s 40 64 40")
    s.tick(40)
    s.shot("10_nether_arrival", "after the dimension teleport")
    px, py, pz = player_xyz(s.info)
    s.cmd(f"/fill {px-7:.0f} {py-1:.0f} {pz-7:.0f} {px+9:.0f} {py-1:.0f} {pz+9:.0f} "
          "minecraft:nether_bricks")
    s.cmd(f"/fill {px-7:.0f} {py:.0f} {pz-7:.0f} {px+9:.0f} {py+5:.0f} {pz+9:.0f} "
          "minecraft:air")
    s.cmd(f"/fill {px-8:.0f} {py+6:.0f} {pz-8:.0f} {px+10:.0f} {py+6:.0f} {pz+10:.0f} "
          "minecraft:nether_bricks")
    s.cmd(f"/fill {px-8:.0f} {py:.0f} {pz+10:.0f} {px+10:.0f} {py+5:.0f} {pz+10:.0f} "
          "minecraft:nether_brick_fence")
    s.cmd(f"/fill {px+3:.0f} {py-1:.0f} {pz+6:.0f} {px+5:.0f} {py-1:.0f} {pz+8:.0f} "
          "minecraft:lava")
    s.cmd("/replaceitem entity @s weapon.mainhand minecraft:diamond_sword")
    s.cmd("/give @s minecraft:diamond_pickaxe")
    s.tick(10)
    settle_chat(s)
    s.shot("11_nether_fortress", "nether brick corridor, sword in hand")
    s.witness("nether_ready")

    killed = False
    for i in range(4):
        if kill_mob(s, "blaze", f"12_blaze{i}", dist=MELEE, dy=1.0,
                    nbt="{NoAI:1b,NoGravity:1b}", attempts=1):
            killed = True
            if gather_drops(s, "blaze_rod", f"13_blaze_rod{i}"):
                break
    s.witness("after_blaze", killed_blaze=killed)
    if not has(s.info, "blaze_rod"):
        logger.warning("[nether] no rod dropped; giving one so the chain continues")
        s.cmd("/give @s minecraft:blaze_rod 2")
        s.tick(6)
        s.shot("14_blaze_rod_given", "GIVEN, not dropped -- chain continuity only")


def stage_blaze_powder(s: Shoot) -> None:
    logger.info("=== stage: blaze powder ===")
    ok = craft_2x2(s, "blaze_powder", "20_blaze_powder")
    s.witness("after_blaze_powder", crafted=ok)
    if not ok:
        s.cmd("/give @s minecraft:blaze_powder 2")
        s.tick(6)


def land_in_end(s: Shoot) -> None:
    """Arrive in the End on top of the island."""
    # Fall onto the island rather than teleporting to a fixed height. (0, 70, 0) put the
    # first run *inside* the terrain: every End frame was the inside of a one-block
    # trench. Resistance IV covers the landing.
    s.cmd("/execute in minecraft:the_end run teleport @s 6 95 6")
    s.tick(30)
    aim_pitch(s, -5.0)
    for i in range(3):
        s.tick(20)
        s.shot(f"30_end_descent{i}", "falling toward the main island")
    last = None
    for _ in range(20):
        s.tick(20)
        y = player_xyz(s.info)[1]
        if last is not None and abs(y - last) < 0.05:
            break
        last = y
    px, py, pz = player_xyz(s.info)
    logger.info(f"[end] landed at {px:.1f},{py:.1f},{pz:.1f}")
    if py < 10:  # fell past the island; give it a floor and try once more
        s.cmd(f"/fill {px-6:.0f} 64 {pz-6:.0f} {px+6:.0f} 64 {pz+6:.0f} minecraft:end_stone")
        s.cmd(f"/teleport @s {px:.1f} 66 {pz:.1f}")
        s.tick(20)
    settle_chat(s)
    aim_pitch(s, 0.0)
    s.shot("31_end_island", "the End: end stone, obsidian pillars, void horizon")
    s.witness("end_ready", mobs=str(s.info.get("mobs"))[:400])

    # A slow look around: the dragon is already in the sky -- it spawns with the End
    # itself, which is why the boss bar is in every frame from here on.
    for i in range(8):
        s.run(P.look(yaw=45.0))
        s.tick(6)
        s.shot(f"31_end_look{i}", "sweep of the island and the sky")


def stage_end(s: Shoot) -> None:
    """Milestones: end_stone, kill_enderman, ender_pearl, eye_of_ender, kill_ender_dragon."""
    logger.info("=== stage: the End ===")
    land_in_end(s)

    # -- end_stone: a `pickup` milestone, so it is mined and walked over
    s.cmd("/replaceitem entity @s weapon.mainhand minecraft:diamond_pickaxe")
    aim_pitch(s, 85.0)
    s.tick(4)
    s.shot("32_end_stone_aim", "looking down at end stone")
    s.run(P.repeat(P.act(attack=1), 60), tag="32_end_stone_mine", every=15)
    s.run(P.repeat(P.noop(), 20))
    s.shot("33_end_stone_broken", "block gone, drop at the feet")
    if not has(s.info, "end_stone"):
        gather_drops(s, "end_stone", "33_end_stone")
    # Mining downward leaves the player standing in the hole it just made, with a block
    # face a hand's width from the camera. Every frame after this point in the previous
    # run -- enderman, dragon, the lot -- was a picture of the inside of that hole, and
    # both mobs were summoned into solid rock. Restore the floor and stand back on it.
    s.cmd(f"/fill {px-5:.0f} {py-1:.0f} {pz-5:.0f} {px+5:.0f} {py-1:.0f} {pz+5:.0f} "
          "minecraft:end_stone")
    s.cmd(f"/fill {px-5:.0f} {py:.0f} {pz-5:.0f} {px+5:.0f} {py+4:.0f} {pz+5:.0f} "
          "minecraft:air")
    s.cmd(f"/teleport @s {px:.2f} {py:.2f} {pz:.2f}")
    s.tick(10)
    aim_pitch(s, 0.0)
    s.shot("33_end_stone_standing", "back on the surface, end stone in the inventory")
    s.witness("after_end_stone", end_stone=has(s.info, "end_stone"))

    # -- enderman and the pearl
    s.cmd("/replaceitem entity @s weapon.mainhand minecraft:diamond_sword")
    aim_pitch(s, 0.0)
    got_pearl = False
    for i in range(4):
        if kill_mob(s, "enderman", f"34_enderman{i}", dist=MELEE, dy=0.1,
                    nbt="{NoAI:1b,PersistenceRequired:1b}", attempts=1, aim_dy=1.3):
            if gather_drops(s, "ender_pearl", f"35_ender_pearl{i}"):
                got_pearl = True
                break
    s.witness("after_enderman", pearl=got_pearl)
    if not has(s.info, "ender_pearl"):
        s.cmd("/give @s minecraft:ender_pearl 1")
        s.tick(6)
        s.shot("35_ender_pearl_given", "GIVEN, not dropped -- chain continuity only")

    # -- eye of ender
    ok = craft_2x2(s, "ender_eye", "36_eye_of_ender")
    s.witness("after_eye_of_ender", crafted=ok)
    if not ok:
        s.cmd("/give @s minecraft:ender_eye 1")
        s.tick(6)
    settle_chat(s)
    s.shot("37_eye_in_hand", "eye of ender in the inventory")

    stage_dragon(s)


def stage_dragon(s: Shoot) -> None:
    """The last milestone. The dragon here is the one the End generated -- the boss bar is
    already in the frame -- so this is the real entity, not a summoned stand-in.

    It is brought to the player and pinned rather than fought: `NoAI` stops the flight
    phases, the crystals are removed because they heal it faster than a sword removes
    health, and its health is set low enough that a few swings finish it. The milestone is
    the `kill_entity` event, and this is the shortest honest path to it.
    """
    logger.info("=== stage: the dragon ===")
    dragon = "@e[type=minecraft:ender_dragon,limit=1]"
    # The crystals heal it faster than a sword takes health off.
    s.cmd("/kill @e[type=minecraft:end_crystal]")
    # DragonPhase 10 is HOVERING. `NoAI` does nothing here: EnderDragon.aiStep runs its
    # flight phases whatever the flag says, which is why the previous run's teleport only
    # displaced it for a moment before it flew off again -- every "close" frame was empty
    # sky. The phase is the thing that holds it still.
    s.cmd(f"/data merge entity {dragon} {{DragonPhase:10}}")
    s.cmd("/effect give @s minecraft:strength 99999 4 true")
    s.tick(10)
    aim_pitch(s, -20.0)
    for i in range(6):
        s.tick(12)
        s.shot(f"40_dragon_flight{i}", "the ender dragon over the island")
    s.witness("dragon_in_view", mobs=str(s.info.get("mobs"))[:400])

    import math

    def bring_dragon(dist: float, up: float, health: float | None = 6.0
                     ) -> tuple[float, float, float]:
        px, py, pz = player_xyz(s.info)
        yaw = player_yaw(s.info)
        fx, fz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        tx, ty, tz = px + fx * dist, py + up, pz + fz * dist
        # Re-merging identical values is an error the game prints in red across the
        # frame ("Nothing changed..."), so the phase is set once and the health is only
        # touched when it actually changes.
        if health is not None:
            # Health varies per call, so the merge always changes something and the phase
            # gets re-asserted for free.
            s.cmd(f"/data merge entity {dragon} {{DragonPhase:10,Health:{health}f}}")
        s.cmd(f"/teleport {dragon} {tx:.2f} {ty:.2f} {tz:.2f}")
        return tx, ty, tz

    # A portrait first, at full health and far enough back for the whole animal to be in
    # frame. Up close it dies on the first swing -- the previous run's only pictures of it
    # were the death beams.
    for i, (dist, up) in enumerate(((22.0, 6.0), (18.0, 5.0), (14.0, 4.0), (11.0, 3.0))):
        tx, ty, tz = bring_dragon(dist, up, health=None)
        s.tick(8)
        acts, _ = P.look_at(s.info, tx, ty, tz)
        s.run(acts)
        s.tick(4)
        # It bobs even while hovering, so this is a burst rather than one exposure.
        for k in range(4):
            s.tick(5)
            s.shot(f"40_dragon_portrait{i}_{k}", f"the dragon, {dist:.0f} blocks out")

    before = has(s.info, "ender_dragon", "kill_entity")
    killed = False
    for attempt, (dist, up, aim) in enumerate(((5.0, 1.0, 1.5), (4.0, 0.5, 0.5),
                                               (6.0, 2.0, 2.5), (3.5, 1.0, 1.0))):
        tx, ty, tz = bring_dragon(dist, up, health=6.0 - attempt)
        s.tick(6)
        s.shot(f"41_dragon_close{attempt}", "the dragon hovering at melee range")
        acts, _ = P.look_at(s.info, tx, ty + aim, tz)
        s.run(acts)
        if attempt == 0:
            s.shot("41_dragon_fight_aimed", "crosshair on the dragon")
        for k in range(12):
            s.run(P.repeat(P.act(attack=1), 2))
            s.run(P.repeat(P.noop(), 8))
            if k in (0, 3, 7):
                s.shot(f"41_dragon_fight{attempt}_swing{k}", "landing hits")
            if k % 4 == 3:  # it drifts even while hovering; bring it back
                bring_dragon(dist, up, health=None)
        s.tick(10)
        if has(s.info, "ender_dragon", "kill_entity") > before:
            killed = True
            break

    if not killed:
        # Melee reach against a body part is finicky; an arrow is credited to the player
        # just the same, and the dragon is hovering still.
        logger.warning("[dragon] melee did not land the kill; trying the bow")
        s.cmd("/replaceitem entity @s weapon.mainhand "
              "minecraft:bow{Enchantments:[{id:\"minecraft:infinity\",lvl:1s}]}")
        s.cmd("/give @s minecraft:arrow 64")
        for attempt in range(4):
            tx, ty, tz = bring_dragon(9.0, 2.0)
            s.tick(6)
            acts, _ = P.look_at(s.info, tx, ty + 1.0, tz)
            s.run(acts)
            s.shot(f"41_dragon_bow{attempt}_aimed", "drawing on the hovering dragon")
            s.run(P.repeat(P.act(use=1), 26))     # full draw
            s.run(P.repeat(P.noop(), 6))          # release
            s.tick(10)
            s.shot(f"41_dragon_bow{attempt}_loosed", "arrow away")
            if has(s.info, "ender_dragon", "kill_entity") > before:
                killed = True
                break

    for i in range(10):
        s.tick(8)
        s.shot(f"42_dragon_death{i}", "death beams" if killed else "after the exchange")
    s.witness("after_dragon", killed_dragon=killed)
    settle_chat(s)
    aim_pitch(s, -10.0)
    s.shot("43_after_the_end", "the island after the dragon")


def stage_dragon_only(s: Shoot) -> None:
    """The dragon on its own, for iterating on the fight without re-running the chain."""
    land_in_end(s)
    s.cmd("/replaceitem entity @s weapon.mainhand minecraft:diamond_sword")
    stage_dragon(s)


STAGES = {
    "nether": stage_nether,
    "blaze_powder": stage_blaze_powder,
    "end": stage_end,
    "dragon_only": stage_dragon_only,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--stages", default="nether,blaze_powder,end")
    args = ap.parse_args()

    out = Path(args.out or (ROOT / "output" / f"endgame_frames_{int(time.time())}"))
    out.mkdir(parents=True, exist_ok=True)
    logger.add(str(out / "run.log"))

    from mcu_worldmodel.env import make_sim
    sim, task, cfg = make_sim(ROOT / "MCU_benchmark/task_configs/longterm/kill_ender_dragon.yaml",
                              out, render_size=RENDER, obs_size=(128, 128),
                              record=True, fast_reset=False)
    s = Shoot(sim, out)
    try:
        s.reset()
        s.shot("00_spawn", "overworld spawn, before any staging")
        for c in PREAMBLE:
            s.cmd(c)
        s.tick(10)
        s.witness("preamble_done")
        for name in args.stages.split(","):
            name = name.strip()
            if not name:
                continue
            try:
                STAGES[name](s)
            except Exception as exc:  # a broken stage must not cost the earlier frames
                logger.exception(f"[stage] {name} failed: {exc}")
    finally:
        (out / "shots.json").write_text(json.dumps(s.shots, indent=2))
        try:
            sim.close()
        except Exception:
            pass
    logger.info(f"{len(s.shots)} frames -> {out/'frames'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
