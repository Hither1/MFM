"""The stronghold -> End stretch of the dragon chain, as verified macros.

Why. After the eye of ender the task asks for the stronghold (found by throwing eyes and
walking where they fly), the portal room's twelve frames filled with eyes, the jump into
the End, end stone in the inventory, and the dragon. No run has ever done any of it, and
each step is again a geometry problem the model cannot do by eye: where did the eye go?
which face of which frame takes the eye? when am I "in" the End? These compose the
coordinate macros of macros_world and the vision loop shape of macros_entity:

- `throw_eye()`: throw an eye of ender and WATCH it with the camera held still: the
  eye is a moving blob against a still view (`vision.find_moving_blob`), its screen x
  gives the bearing it flew (a pinhole at ~100 degrees horizontal FOV: 268 px of focal
  length for a 640-wide frame), its screen y trend says whether it climbed or dropped.
  The eye never drops back in this engine (seven throws, no item entity), so each throw
  costs an eye; `fetch=True` keeps the walk-out along the bearing for one where it does.
  Measured on this engine (a probe): the sprite is ~100 px at tick 15
  after the throw, 16 px by tick 30, gone from the diff after 33; the first 12 ticks show
  only the hand animation in the lower right.
- `travel_bearing(yaw, blocks)`: walk a heading for a distance in closed-loop legs.
- `fill_end_portal(x, y, z)`: the 12 frames around the 3x3 pit centred on (x, y, z);
  stand outside each and right-click its outer face with an eye; a frame that refuses
  the eye already has one. Resumable across the plan cap.
- `enter_end(x, y, z)`: walk onto the activated portal and wait for the coordinate
  jump (the End spawn is an obsidian platform near x=100, z=0 in every world).
- `mine_end_stone(yaw, pitch)`: a pickaxe on the pale ground toward the island.
- `break_crystal(shots)`: find the end crystal (a bright magenta/white cube on an
  obsidian tower), shoot it with the bow or, when close and no bow is carried, hit it.
- `attack_dragon(ticks)`: melee the dragon while it is in reach (perched), verified on
  custom.damage_dealt and kill_entity.ender_dragon.

Nothing here reads a scoring rule; every fact is the game's own (the End portal, the
platform at x=100, the crystals, the perch).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from mcu_worldmodel import gui, macros, vision
from mcu_worldmodel import macros_world as MW
from mcu_worldmodel import macros_entity as ME

#: Horizontal field of view the frames are rendered with (measured in a staged scene: a mob
#: exactly 40 degrees off the facing rendered 225 px right of centre in a 640-wide frame,
#: which a pinhole at 100 degrees predicts). The focal length in pixels is width/2/tan(50).
HFOV_DEG = 100.0
#: The obsidian spawn platform of the End (vanilla), and how far a point may be from it
#: to still count as "on it".
END_PLATFORM_X, END_PLATFORM_Z = 100.0, 0.0
END_PLATFORM_TOL = 12.0
#: A teleport is a position jump longer than any walk in one tick.
JUMP_MIN = 40.0
#: Ticks to stand in the End portal before giving up (it fires within a few ticks).
END_WAIT = 120
#: Eye tracking: ticks after the throw before the diff is read (the hand animation of
#: the throw is a moving blob of its own in the lower right for ~12 ticks), the watch
#: window, and the corner the hand occupies (fraction of width / height).
EYE_SKIP_TICKS = 12
EYE_WATCH_TICKS = 50
EYE_HAND_X, EYE_HAND_Y = 0.72, 0.52
#: The eye flies ~12 blocks out before it hovers and drops; the fetch walks that far,
#: and waits this many ticks after the throw before sweeping for the drop.
EYE_RANGE = 12.0
EYE_DROP_TICKS = 70       # counted from the end of the watch (~50 ticks after the throw)
#: Screen-y slope (px per tick, + is down) beyond which the eye is read as descending.
EYE_DOWN_SLOPE = 1.5
#: End crystal colours: magenta/pink faces and a bright white core, on the near-black
#: End sky or grey obsidian. Bands on the frame body; refined on the frames of a staged scene.
_CRYSTAL_MIN_PX = 16
#: The dragon is black; the End sky is not quite (v 18-26 measured).
#: Body pixels at or below this brightness are the dragon.
DRAGON_V_MAX = 12
DRAGON_MIN_PX = 250

#: What the last throw_eye measured, for the fetch that follows and the model.
LAST_EYE: dict[str, Any] = {}
#: The last portal fill: its centre and the frames already holding an eye.
LAST_PORTAL: dict[str, Any] = {}


# -- geometry helpers ----------------------------------------------------------------

def focal_px(width: int) -> float:
    return (width / 2.0) / math.tan(math.radians(HFOV_DEG / 2.0))


def bearing_of_pixel(x: float, width: int, yaw: float) -> float:
    """The world yaw of a screen column `x` seen from a camera at `yaw`."""
    rel = math.degrees(math.atan((x - width / 2.0) / focal_px(width)))
    return (yaw + rel + 180.0) % 360.0 - 180.0


def bearing_from_samples(samples: list[tuple[int, float, float]], width: int,
                         yaw: float) -> tuple[float, float, float] | None:
    """(bearing, rel_deg, y_slope) from (t, x, y) samples of the eye in flight."""
    if not samples:
        return None
    xs = sorted(s[1] for s in samples)
    mx = xs[len(xs) // 2]
    rel = math.degrees(math.atan((mx - width / 2.0) / focal_px(width)))
    slope = 0.0
    if len(samples) >= 2:
        ts = np.array([s[0] for s in samples], dtype=np.float64)
        ys = np.array([s[2] for s in samples], dtype=np.float64)
        if ts.max() > ts.min():
            slope = float(np.polyfit(ts, ys, 1)[0])
    return ((yaw + rel + 180.0) % 360.0 - 180.0, rel, slope)


def _norm(yaw: float) -> float:
    return (yaw + 180.0) % 360.0 - 180.0


def _hand_blob(x: float, y: float, w: int, h: int) -> bool:
    return x > w * EYE_HAND_X and y > h * EYE_HAND_Y


# -- throw_eye ----------------------------------------------------------------------

def throw_eye(cur, info: dict, fetch: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Throw one eye of ender and watch where it flies. `fetch` walks out along the
    bearing afterwards for a dropped eye -- off by default: in this engine the eye never
    drops back (a probe: seven throws, no ender_eye item entity at any
    tick after any of them, while a summoned one is found at once), so every throw
    consumes the eye."""
    from mcu_worldmodel import procedures as P

    have = sum(q for _, q in gui.find_slots(info, "ender_eye"))
    if have < 1:
        return [], ("throw_eye: you carry no ender_eye (blaze_powder + ender_pearl in the "
                    "2x2 grid).")
    acts, err = MW._prep_item(cur, info, "ender_eye", "throw_eye")
    if err:
        return [], err
    # A little above level: the eye climbs as it flies and must stay in the view.
    acts += P.look_abs(pitch=-12, ticks=24)
    budget = EYE_SKIP_TICKS + EYE_WATCH_TICKS + 80
    acts.append(macros.marker("_eyetrack", {
        "t": 0, "phase": "throw", "still": 0, "samples": [], "yaw0": None, "pitch0": None,
        "base": None, "budget": budget, "miss": 0, "sweep": 0, "last_seen": None,
        "head": []}, budget))
    if fetch:
        acts.append(macros.marker("_eyefetch", {"t": 0, "phase": "walk", "budget": 330,
                                                "walk": None, "sweep_i": 0, "base": None},
                                  330))
    return acts, (f"throw_eye: {have} carried; throwing one and watching its flight"
                  + (", then walking out to look for it" if fetch else ""))


def _eye_detect(agent, st: dict[str, Any]) -> tuple[float, float, int] | None:
    """(x, y, n_px) of the eye in the current frame against the previous one."""
    prev, cur = agent._prev_pov, agent._last_pov
    if prev is None or cur is None:
        return None
    m = vision.find_moving_blob(prev, cur, min_px=12)
    if m is None:
        return None
    x, y, n, w, h = m
    fh, fw = np.asarray(cur).shape[0], np.asarray(cur).shape[1]
    if _hand_blob(x, y, fw, fh):
        return None
    return (float(x), float(y), int(n))


def _eye_colour(agent) -> tuple[float, float, int] | None:
    """A saturated green blob above the horizon (the eye hovering far off, or still
    when the camera is not): (x, y, n_px) or None."""
    cur = agent._last_pov
    if cur is None:
        return None
    f = np.asarray(cur)
    if f.ndim != 3:
        return None
    keep = vision._body_mask(f)
    body = f[: keep.shape[0]].astype(np.float32)
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    mask = (g > r + 28) & (g > b + 28) & (g >= 70) & keep
    mask = vision._erode4(mask)
    if not mask.any():
        return None
    comps = vision._components(mask)
    for c in comps:
        if c["n"] < 20:
            break
        if c["n"] > 4000 or c["h"] > 60:
            continue                      # foliage, not a sprite
        # the eye is a sprite in the open: its ring must be mostly non-green
        ok, inner, ring = vision._isolated(mask, c)
        if ok and inner >= 0.3:
            return (float(c["cx"]), float(c["cy"]), int(c["n"]))
    return None


@macros.tick("_eyetrack", shrink="budget")
def _eyetrack_tick(agent, st: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail("throw_eye: a screen is open; close it first.", "eye_gui_flush")
        return None
    if pos is None:
        return mk_act()
    ME._track(agent, st)
    t = st["t"]
    st["t"] += 1
    if st["base"] is None:
        st["base"] = {"eyes": agent._cur_inv.get("ender_eye", 0),
                      "use": agent.stat_now("use_item", "ender_eye")}
        st["yaw0"], st["pitch0"] = float(pos["yaw"]), float(pos["pitch"])
    frame = agent._last_pov
    fw = int(np.asarray(frame).shape[1]) if frame is not None else 640

    def finish(bearing_info, how: str) -> None:
        eyes = agent._cur_inv.get("ender_eye", 0)
        thrown = st["base"]["eyes"] - eyes
        if bearing_info is None:
            LAST_EYE.clear()
            agent._note_failure("throw_eye")
            agent.memory.add_note(
                f"throw_eye: {'the eye left your hand (' + str(eyes) + ' left)' if thrown >= 1 else 'no eye left your hand (' + str(eyes) + ' carried)'}"
                f" but it was never seen in the view -- it flew out of the ~100-degree "
                f"field (behind you, or nearly straight up because the stronghold is very "
                f"close). Turn 180 degrees (look_abs) and throw again, or scan_around first.")
            return
        bearing, rel, slope = bearing_info
        down = slope > EYE_DOWN_SLOPE
        LAST_EYE.clear()
        LAST_EYE.update({"bearing": bearing, "rel": rel, "down": down,
                         "from": (pos["x"], pos["z"]), "step": agent.step,
                         "eyes_before": st["base"]["eyes"]})
        agent.cursor_stats["eyes_thrown"] = agent.cursor_stats.get("eyes_thrown", 0) + 1
        side = ("straight ahead" if abs(rel) < 4 else
                f"{abs(rel):.0f} degrees {'right' if rel > 0 else 'left'} of your facing")
        agent.memory.add_note(
            f"throw_eye: the eye flew toward yaw {bearing:.0f} ({side}, seen {how}) and "
            + ("went DOWN as it flew: the stronghold is BELOW you, within ~12 blocks -- "
               "dig_down here (its rooms are stone brick; look for the portal room's 12 "
               "frames around a lava pit)."
               if down else
               f"climbed as it flew: the stronghold is farther that way -- travel_bearing("
               f"yaw={bearing:.0f}, blocks=100) and throw again; when an eye drops instead "
               f"of climbing you are on top of it.")
            + f" Eyes carried: {eyes} (a throw uses the eye up here; it does not drop back).")

    if st["phase"] == "throw":
        st["phase"] = "watch"
        return ME._still(st, mk_act(use=1))
    if st["phase"] == "watch":
        if t >= EYE_SKIP_TICKS and int(st.get("still", 0)) >= ME.STILL_MIN and ME._steady(st):
            hit = _eye_detect(agent, st)
            if hit is not None:
                st["samples"].append((t, hit[0], hit[1]))
                st["last_seen"] = t
        seen = len(st["samples"])
        gone = st["last_seen"] is not None and t - st["last_seen"] >= 8
        if t >= EYE_SKIP_TICKS + EYE_WATCH_TICKS or (seen >= 4 and gone):
            if seen >= 2:
                finish(bearing_from_samples(st["samples"], fw, st["yaw0"]),
                       f"{seen} frames")
                return None
            # not seen: sweep the camera around, the eye hovers for a couple of seconds
            st["phase"], st["sweep"], st["still"] = "sweep", 0, 0
        return ME._still(st, mk_act())
    # sweep: five 72-degree turns, four still ticks each, colour + motion
    i = st["sweep"]
    if i >= 5 * 6:
        finish(None, "")
        return None
    st["sweep"] += 1
    if i % 6 == 0:
        return ME._still(st, mk_act(camera=[0.0, 30.0]))
    if i % 6 in (1, 2):
        return ME._still(st, mk_act(camera=[0.0, 21.0 if i % 6 == 1 else 21.0]))
    c = _eye_colour(agent)
    if c is None and int(st.get("still", 0)) >= 2 and ME._steady(st):
        c = _eye_detect(agent, st)
    if c is not None:
        finish((bearing_of_pixel(c[0], fw, float(pos["yaw"])),
                _norm(bearing_of_pixel(c[0], fw, float(pos["yaw"])) - st["yaw0"]), 0.0),
               "after turning to look for it")
        return None
    return ME._still(st, mk_act())


@macros.tick("_eyefetch", shrink="budget", moving=True)
def _eyefetch_tick(agent, ef: dict[str, Any], mk_act):
    """Walk out along the measured bearing and sweep for the dropped eye."""
    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail("throw_eye: a screen is open; close it first.", "eye_gui_flush")
        return None
    if pos is None:
        return mk_act()
    if ef["base"] is None:
        ef["base"] = {"eyes": agent._cur_inv.get("ender_eye", 0)}
        if not LAST_EYE or agent.step - LAST_EYE.get("step", -999) > 400:
            return None
        b = math.radians(LAST_EYE["bearing"])
        fx, fz = LAST_EYE["from"]
        ax, az = -math.sin(b), math.cos(b)          # along the bearing
        px, pz = az, -ax                            # across it
        # Waypoints: out to 6 blocks, then a zigzag from 7 to 14 blocks along the
        # bearing, 1.5 blocks either side -- the eye stops anywhere between ~8 and
        # 12 blocks out and the item is picked up within a block of the avatar.
        pts = [(fx + ax * 6, fz + az * 6)]
        side = 1.0
        for d in (7.5, 9.0, 10.5, 12.0, 13.5):
            pts.append((fx + ax * d + px * 1.5 * side, fz + az * d + pz * 1.5 * side))
            side = -side
        ef["points"] = pts
        ef["k"] = 0
        ef["walk"] = {"spot": list(pts[0]), "t": 0}
        ef["start_eyes"] = LAST_EYE.get("eyes_before", ef["base"]["eyes"] + 1)
    ef["t"] += 1
    eyes = agent._cur_inv.get("ender_eye", 0)

    def finish(why: str) -> None:
        got = eyes > ef["base"]["eyes"]
        agent.cursor_stats["eyes_fetched"] = agent.cursor_stats.get("eyes_fetched", 0) + int(got)
        agent.memory.add_note(
            f"throw_eye: {'the eye was picked back up' if got else 'the eye was not found'}"
            f" ({eyes} carried) -- {why}"
            + ("" if got else " One throw in five shatters the eye; if it dropped, it lies "
                              "on the ground 8-12 blocks out along the bearing (collect_drops "
                              "there)."))

    if eyes > ef["base"]["eyes"]:
        finish("it lay along the bearing.")
        return None
    if ef["t"] > ef["budget"]:
        finish("budget spent.")
        return None
    if ef["phase"] == "walk":
        status, action = MW._walk_step(agent, ef["walk"], mk_act, sneak=False)
        if status == "run":
            return action
        ef["phase"] = "wait"
        return mk_act()
    if ef["phase"] == "wait":
        # In vanilla the eye flies ~80 ticks, then drops from ~10 blocks up. Here the
        # eye entity is gone by tick 60 and no item follows (measured).
        if agent.step - LAST_EYE.get("step", agent.step) < EYE_DROP_TICKS:
            return mk_act()
        ef["phase"] = "zigzag"
        ef["k"] = 1
        ef["walk"] = {"spot": list(ef["points"][1]), "t": 0}
        return mk_act()
    # zigzag through the waypoints
    status, action = MW._walk_step(agent, ef["walk"], mk_act, sneak=False)
    if status == "run":
        return action
    ef["k"] += 1
    if ef["k"] >= len(ef["points"]):
        finish("walked a zigzag 6-14 blocks out along the bearing.")
        return None
    ef["walk"] = {"spot": list(ef["points"][ef["k"]]), "t": 0}
    return mk_act()


# -- travel_bearing --------------------------------------------------------------------

def travel_bearing(cur, info: dict, yaw: float = 0.0, blocks: float = 60.0
                   ) -> tuple[list[dict[str, Any]], str]:
    """Walk `blocks` along world heading `yaw`, in closed-loop legs, and say how far."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "travel_bearing: no position yet."
    try:
        yaw, blocks = float(yaw), float(blocks)
    except (TypeError, ValueError):
        return [], "travel_bearing: yaw and blocks must be numbers."
    blocks = max(2.0, min(400.0, blocks))
    dx, dz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    acts: list[dict[str, Any]] = []
    done = 0.0
    while done < blocks - 1e-6:
        leg = min(24.0, blocks - done)
        done += leg
        acts += P.go_to(pos["x"] + dx * done, pos["z"] + dz * done, within=1.5,
                        n=int(leg * 6) + 40)
    acts.append(macros.marker("_bearingreport", {"x0": pos["x"], "z0": pos["z"],
                                                 "yaw": yaw, "blocks": blocks, "t": 0}, 2))
    return acts, (f"travel_bearing: {blocks:.0f} blocks toward yaw {yaw:.0f} in "
                  f"{len(acts) - 1} legs")


@macros.tick("_bearingreport")
def _bearingreport_tick(agent, br: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    d = math.hypot(pos["x"] - br["x0"], pos["z"] - br["z0"])
    agent.cursor_stats["bearing_blocks"] = agent.cursor_stats.get("bearing_blocks", 0) + int(d)
    agent.memory.add_note(
        f"travel_bearing: {d:.0f} of {br['blocks']:.0f} blocks covered toward yaw "
        f"{br['yaw']:.0f}, now at ({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})."
        + (" Short: a go_to note above says what blocked the walk -- route around it and "
           "call again." if d < br["blocks"] - 3 else ""))
    return None


# -- fill_end_portal ---------------------------------------------------------------------

def portal_frames(cx: int, cy: int, cz: int) -> list[dict[str, Any]]:
    """The 12 frame cells around the 3x3 pit centred on (cx, cy, cz), each with the
    outer face to click and the standing spot outside it, in walking order around the
    ring (north row west->east, east column, south row east->west, west column)."""
    out = []
    ring = ([(-2 + k, -2) for k in range(1, 4)]            # north row
            + [(2, -2 + k) for k in range(1, 4)]           # east column
            + [(2 - k, 2) for k in range(1, 4)]            # south row
            + [(-2, 2 - k) for k in range(1, 4)])          # west column
    for dx, dz in ring:
        if abs(dx) == 2:
            sx, sz = (1 if dx > 0 else -1), 0
            face = "east" if dx > 0 else "west"
        else:
            sx, sz = 0, (1 if dz > 0 else -1)
            face = "south" if dz > 0 else "north"
        out.append({"cell": (cx + dx, cy, cz + dz), "face": face,
                    "spot": (cx + dx + sx + 0.5, cz + dz + sz + 0.5),
                    "alt": (cx + 2 * (sx if sx else (1 if dx > 0 else -1)) + 0.5,
                            cz + 2 * (sz if sz else (1 if dz > 0 else -1)) + 0.5)})
    return out


def fill_end_portal(cur, info: dict, x: float = 0.0, y: float = 0.0, z: float = 0.0
                    ) -> tuple[list[dict[str, Any]], str]:
    """Put an eye of ender into every empty frame of the End portal whose 3x3 pit is
    centred on (x, y, z) at the frames' level. Walks around the ring outside it."""
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "fill_end_portal: no position yet."
    try:
        cx, cy, cz = math.floor(float(x)), math.floor(float(y)), math.floor(float(z))
    except (TypeError, ValueError):
        return [], f"fill_end_portal: bad coordinates {x!r}, {y!r}, {z!r}"
    frames = portal_frames(cx, cy, cz)
    centre = (cx, cy, cz)
    if LAST_PORTAL.get("centre") != centre:
        LAST_PORTAL.clear()
        LAST_PORTAL.update({"centre": centre, "filled": [], "refused": []})
    done = {tuple(c) for c in LAST_PORTAL["filled"]} | {tuple(c) for c in LAST_PORTAL["refused"]}
    todo = [f for f in frames if tuple(f["cell"]) not in done]
    if not todo:
        return [], ("fill_end_portal: every frame of this portal has been visited (eyes "
                    f"placed in {len(LAST_PORTAL['filled'])}, {len(LAST_PORTAL['refused'])} "
                    "already held one). enter_end(x, y, z) next.")
    have = sum(q for _, q in gui.find_slots(info, "ender_eye"))
    if have < 1:
        return [], (f"fill_end_portal: you carry no ender_eye ({len(todo)} frames of this "
                    f"portal are still unvisited).")
    acts, err = MW._prep_item(cur, info, "ender_eye", "fill_end_portal")
    if err:
        return [], err
    # start with the nearest frame, keep the ring order from there
    k0 = min(range(len(todo)), key=lambda i: math.hypot(todo[i]["spot"][0] - pos["x"],
                                                        todo[i]["spot"][1] - pos["z"]))
    todo = todo[k0:] + todo[:k0]
    budget = len(todo) * 120 + 40
    acts.append(macros.marker("_fillportal", {
        "frames": [{"cell": list(f["cell"]), "face": f["face"], "spot": list(f["spot"]),
                    "alt": list(f["alt"])} for f in todo],
        "i": 0, "placed": 0, "refused": 0, "unreached": 0, "sub": None, "walk": None,
        "alt_tried": False, "budget": budget, "used": 0, "centre": list(centre)}, budget))
    return acts, (f"fill_end_portal: {len(todo)} frames to visit around ({cx}, {cy}, {cz}) "
                  f"with {have} eyes; a frame that refuses the eye already holds one. A "
                  f"plan holds ~400 ticks: call again from the same portal to continue.")


#: The frame's top seen from one block away with the crosshair on its centre: the
#: EMPTY socket is a dark square, the eye a green iris. A 17x17 patch around the
#: crosshair, measured on probe frames: empty -> green share 0.00 and a
#: median brightness of 25 at 1-3 blocks; with an eye -> green share 0.76 / median 100
#: at 1 block, 0.34 / 84 at 2 blocks, 0.18 / 45 at 3 blocks (too far to read).
EYE_PATCH_RAD = 8
EYE_GREEN_SHARE_MIN = 0.30
EYE_V_MEDIAN_MIN = 70.0


def frame_top_reading(frame) -> tuple[float, float, float, float] | None:
    """(green_share, median_v, mean_g_minus_r, mean_g_minus_b) of the patch under the
    crosshair -- the top of the frame the camera was steered onto."""
    if frame is None:
        return None
    f = np.asarray(frame)
    if f.ndim != 3:
        return None
    h, w = f.shape[0], f.shape[1]
    r0 = EYE_PATCH_RAD
    patch = f[h // 2 - r0:h // 2 + r0 + 1, w // 2 - r0:w // 2 + r0 + 1].reshape(-1, 3).astype(np.float32)
    if patch.size == 0:
        return None
    r, g, b = patch[:, 0], patch[:, 1], patch[:, 2]
    green = float(((g > r + 15) & (g > b + 5) & (g > 60)).mean())
    v = float(np.median(np.maximum(np.maximum(r, g), b)))
    return (green, v, float((g - r).mean()), float((g - b).mean()))


def frame_has_eye(frame) -> bool | None:
    rd = frame_top_reading(frame)
    if rd is None:
        return None
    return rd[0] >= EYE_GREEN_SHARE_MIN or (rd[1] >= EYE_V_MEDIAN_MIN and rd[0] >= 0.15)


@macros.tick("_fillportal", shrink="budget", moving=True)
def _fillportal_tick(agent, fp: dict[str, Any], mk_act):
    """Per frame: walk to its outside spot, steer the crosshair onto the centre of its
    TOP face, read whether an eye is already there (a click on a filled frame -- or a
    click that misses the frame -- THROWS the eye instead: a staged scene threw all
    twelve), click the top with the eye when it is empty, then look again and read the
    eye that should now be there."""
    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail("fill_end_portal: a screen is open; close it first.",
                          "fillportal_gui_flush")
        return None
    if pos is None:
        return mk_act()
    fp["used"] += 1
    n = len(fp["frames"])

    def finish(why: str) -> None:
        agent.cursor_stats["portal_eyes"] = agent.cursor_stats.get("portal_eyes", 0) + fp["placed"]
        total = len(LAST_PORTAL.get("filled", []))
        rest = n - fp["i"]
        cx, cy, cz = fp["centre"]
        agent.memory.add_note(
            f"fill_end_portal: {fp['placed']} eye(s) placed this call ({total} in all), "
            f"{fp['refused']} frame(s) already held an eye, "
            f"{fp['unreached']} could not be reached or took no eye"
            + (f", {rest} not attempted" if rest else "") + f". {why}"
            + (f" When all 12 frames hold an eye the pit fills with the black portal: "
               f"enter_end(x={cx}, y={cy}, z={cz})." if rest == 0 else
               " Call fill_end_portal again with the same centre to continue."))

    if fp["i"] >= n:
        finish("Done.")
        return None
    if fp["used"] > fp["budget"]:
        finish("Budget spent.")
        return None
    f = fp["frames"][fp["i"]]
    cell = tuple(int(v) for v in f["cell"])
    top = (cell[0] + 0.5, cell[1] + 0.81, cell[2] + 0.5)
    phase = fp.get("phase") or "walk"

    def next_frame(outcome: str) -> None:
        if outcome == "placed":
            fp["placed"] += 1
            LAST_PORTAL.setdefault("filled", []).append(list(cell))
        elif outcome == "refused":
            fp["refused"] += 1
            LAST_PORTAL.setdefault("refused", []).append(list(cell))
        else:
            fp["unreached"] += 1
        fp["sub"], fp["walk"], fp["phase"], fp["alt_tried"], fp["t"] = None, None, "walk", False, 0
        fp["i"] += 1

    if phase == "walk":
        _, _, dist = MW.angles_to(pos, top)
        spot = f["alt"] if fp["alt_tried"] else f["spot"]
        far = dist > MW.REACH - 0.8 or math.hypot(pos["x"] - spot[0], pos["z"] - spot[1]) > 1.2
        if far and fp["walk"] is None:
            fp["walk"] = {"spot": list(spot), "t": 0}
        if fp["walk"] is not None:
            status, action = MW._walk_step(agent, fp["walk"], mk_act, sneak=False)
            if status == "run":
                return action
            fp["walk"] = None
            if status == "failed":
                _, _, dist = MW.angles_to(pos, top)
                if dist > MW.REACH - 0.3:
                    if not fp["alt_tried"]:
                        fp["alt_tried"] = True
                        return mk_act()
                    next_frame("unreached")
                    return mk_act()
        fp["phase"], fp["t"] = "look", 0
        return mk_act()
    if phase in ("look", "relook"):
        pitch, yaw, _ = MW.angles_to(pos, top)
        dp = pitch - pos["pitch"]
        dy = MW.norm_yaw_delta(yaw, pos["yaw"])
        fp["t"] += 1
        if (abs(dp) > 1.0 or abs(dy) > 1.0) and fp["t"] <= 40:
            return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
        # the rendered frame lags the heading by a tick: two still ticks, then read
        if fp["t"] < 43 and fp.get("settle", 0) < 2:
            fp["settle"] = fp.get("settle", 0) + 1
            return mk_act()
        fp["settle"] = 0
        has = frame_has_eye(agent._last_pov)
        fp["reading"] = frame_top_reading(agent._last_pov)
        if phase == "look":
            if has:
                next_frame("refused")
                return mk_act()
            fp["phase"] = "click"
            fp["sub"] = MW.new_use_state(cell, "ender_eye", "above", "use", 2,
                                         "fill_end_portal", tol=1.0, faces=[])
            return mk_act()
        # relook after the click
        next_frame("placed" if has else "unreached")
        if not has:
            agent.memory.add_note(
                f"fill_end_portal: the frame at {cell} shows no eye after the click "
                f"(the eye was probably THROWN: the click missed the frame's top). "
                f"Eyes carried: {agent._cur_inv.get('ender_eye', 0)}.")
        return mk_act()
    # click
    status, action = MW.use_step(agent, fp["sub"], mk_act)
    if status == "run":
        return action
    fp["sub"] = None
    if status == "failed":
        next_frame("unreached")
        return mk_act()
    fp["phase"], fp["t"] = "relook", 0
    return mk_act()


# -- enter_end ----------------------------------------------------------------------------

def enter_end(cur, info: dict, x: float = 0.0, y: float = 0.0, z: float = 0.0
              ) -> tuple[list[dict[str, Any]], str]:
    """Walk onto the activated End portal (the pit centred on x, y, z) and wait."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "enter_end: no position yet."
    try:
        cx, cz = math.floor(float(x)) + 0.5, math.floor(float(z)) + 0.5
    except (TypeError, ValueError):
        return [], f"enter_end: bad coordinates {x!r}, {y!r}, {z!r}"
    acts = P.go_to(cx, cz, within=0.5, n=160)
    acts.append(macros.marker("_endcheck", {"t": 0, "n": END_WAIT, "x": cx, "z": cz,
                                            "pos0": None, "y_low": None}, END_WAIT))
    return acts, f"enter_end: walking onto ({cx:.1f}, {cz:.1f}) and waiting for the End"


def in_the_end(pos: dict[str, float]) -> bool:
    return (abs(pos["x"] - END_PLATFORM_X) <= END_PLATFORM_TOL
            and abs(pos["z"] - END_PLATFORM_Z) <= END_PLATFORM_TOL)


@macros.tick("_endcheck", shrink="n")
def _endcheck_tick(agent, ec: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    if ec["pos0"] is None:
        ec["pos0"] = (pos["x"], pos["y"], pos["z"])
    jumped = math.dist(ec["pos0"], (pos["x"], pos["y"], pos["z"])) > JUMP_MIN
    if jumped:
        agent.cursor_stats["end_trips"] = agent.cursor_stats.get("end_trips", 0) + 1
        agent._dimension = "the End"
        yaw_island = math.degrees(math.atan2(pos["x"], -pos["z"])) if (pos["x"] or pos["z"]) else 90.0
        # yaw toward (0, 0): facing (-sin yaw, cos yaw) = (-x, -z)/r  ->  yaw = atan2(x, -z)
        agent.memory.add_note(
            f"enter_end: you are in THE END at ({pos['x']:.0f}, {pos['y']:.0f}, "
            f"{pos['z']:.0f})"
            + (" on the obsidian spawn platform" if in_the_end(pos) else "")
            + f". The island (pale end stone, the obsidian towers with the crystals, the "
              f"dragon) lies toward x 0, z 0 -- yaw {yaw_island:.0f}. mine_end_stone() "
              f"digs the nearest end stone; the void below the platform's edge is death, "
              f"bridge_forward toward the island when there is a gap.")
        return None
    ec["t"] += 1
    if ec["t"] >= ec["n"]:
        d = math.hypot(pos["x"] - ec["x"], pos["z"] - ec["z"])
        agent._note_failure("enter_end")
        agent.memory.add_note(
            f"enter_end: no teleport after {ec['t']} ticks"
            + (f", {d:.1f} blocks from the pit centre -- walk INTO the pit (jump onto the "
               f"frame ring first; go_to with within=0.4)." if d > 1.2 else
               " while standing in the pit -- the portal is not active: every one of the "
               "12 frames must hold an eye (fill_end_portal again; a refused frame already "
               "has one, an unreached one does not)."))
        return None
    d = math.hypot(ec["x"] - pos["x"], ec["z"] - pos["z"])
    if d > 0.35:
        yaw_t = math.degrees(math.atan2(-(ec["x"] - pos["x"]), ec["z"] - pos["z"]))
        dy = MW.norm_yaw_delta(yaw_t, pos["yaw"])
        if abs(dy) > 12.0:
            return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
        return mk_act(forward=1, jump=1, camera=[0.0, max(-6.0, min(6.0, dy))])
    return mk_act()


# -- mine_end_stone ------------------------------------------------------------------------

def mine_end_stone(cur, info: dict, yaw: float | None = None, pitch: float = 30.0,
                   ticks: int = 240) -> tuple[list[dict[str, Any]], str]:
    """Aim at the ground toward the island (or `yaw`) and dig until end_stone lands."""
    from mcu_worldmodel import procedures as P
    from mcu_worldmodel import macros_gui as MG
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "mine_end_stone: no position yet."
    pick = next((p for p in ("netherite_pickaxe", "diamond_pickaxe", "iron_pickaxe",
                             "stone_pickaxe", "golden_pickaxe", "wooden_pickaxe")
                 if gui.find_slots(info, p)), None)
    if pick is None:
        return [], "mine_end_stone: you carry no pickaxe."
    acts, hot, err = MG.ensure_hotbar(cur, info, pick, "mine_end_stone")
    if err:
        return [], err
    acts += P.equip_hotbar(hot + 1)
    if yaw is None:
        yaw = math.degrees(math.atan2(pos["x"], -pos["z"])) if (pos["x"] or pos["z"]) else 90.0
    pitch = max(-30.0, min(80.0, float(pitch)))
    acts += P.look_abs(pitch=pitch, yaw=float(yaw), ticks=30)
    acts += MG.mine_until("end_stone", 1, max(60, min(400, int(ticks))))
    acts += P.collect_drops(40)
    acts.append(macros.marker("_endstonecheck", {"t": 0, "base": None, "yaw": float(yaw),
                                                 "pitch": pitch}, 4))
    return acts, (f"mine_end_stone: {pick} on whatever is at pitch {pitch:.0f}, yaw "
                  f"{yaw:.0f} until an end_stone lands")


@macros.tick("_endstonecheck")
def _endstonecheck_tick(agent, es: dict[str, Any], mk_act):
    if es["base"] is None:
        es["base"] = agent.stat_now("pickup", "end_stone")
    if es["t"] < 3:
        es["t"] += 1
        return mk_act()
    have = agent._cur_inv.get("end_stone", 0)
    if have >= 1:
        agent.cursor_stats["end_stone"] = agent.cursor_stats.get("end_stone", 0) + 1
        agent.memory.add_note(f"mine_end_stone: end_stone in the inventory ({have}).")
    else:
        agent._note_failure("mine_end_stone")
        agent.memory.add_note(
            f"mine_end_stone: nothing landed -- what is at pitch {es['pitch']:.0f}, yaw "
            f"{es['yaw']:.0f} is not end stone (the spawn platform is obsidian, and past its "
            f"edge is the void). Face the pale yellow ground (scan_around) and call again "
            f"with that yaw, or bridge_forward toward the island first.")
    return None


# -- end crystals and the dragon -------------------------------------------------------------

def crystal_blob(frame) -> tuple[float, float, int, int, int] | None:
    """(x, y, n_px, w, h) of the brightest magenta/white cluster in the frame body."""
    if frame is None:
        return None
    f = np.asarray(frame)
    if f.ndim != 3:
        return None
    keep = vision._body_mask(f)
    body = f[: keep.shape[0]].astype(np.float32)
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    mn = np.minimum(np.minimum(r, g), b)
    # The cube: magenta faces in daylight, pale blue-white in the End's dark (measured
    # 160,192,192 on a staged scene), a white core; and the FIRE under it (180+ red, little
    # blue), which nothing else in the End shows.
    magenta = (r > 110) & (b > 110) & (g < 0.80 * np.minimum(r, b))
    white = (mn > 215)
    bluewhite = (b > 170) & (b > r + 15) & (g > 120)
    fire = (r > 180) & (g > 80) & (g < 200) & (b < 90)
    cube = vision._erode4((magenta | white | bluewhite) & keep)
    fire_m = vision._erode4(fire & keep)
    area = float(keep.sum())
    best = None
    if cube.any():
        for c in vision._components(cube):
            if c["n"] < _CRYSTAL_MIN_PX:
                break
            if c["n"] > 0.08 * area:
                continue                    # the sky, not a cube
            x0, y0, w, h = int(c["x0"]), int(c["y0"]), int(c["w"]), int(c["h"])
            below = fire_m[y0:min(fire_m.shape[0], y0 + 2 * h + 4), max(0, x0 - 4):x0 + w + 4]
            near_fire = int(below.sum()) if below.size else 0
            score = c["n"] + 4 * near_fire
            if best is None or score > best[0]:
                best = (score, c)
    if best is None and fire_m.any():
        for c in vision._components(fire_m):
            if c["n"] < 20:
                break
            if c["n"] > 0.08 * area:
                continue
            # the cube sits just above its fire
            return (float(c["cx"]), float(c["cy"]) - float(c["h"]), int(c["n"]), int(c["w"]), int(c["h"]))
    if best is None:
        return None
    c = best[1]
    return (float(c["cx"]), float(c["cy"]), int(c["n"]), int(c["w"]), int(c["h"]))


def dragon_blob(frame) -> tuple[float, float, int, int, int] | None:
    """(x, y, n_px, w, h) of the largest near-black mass in the frame body (the dragon
    against the End sky, which is not quite black)."""
    if frame is None:
        return None
    f = np.asarray(frame)
    if f.ndim != 3:
        return None
    keep = vision._body_mask(f)
    body = f[: keep.shape[0]].astype(np.float32)
    mx = np.maximum(np.maximum(body[..., 0], body[..., 1]), body[..., 2])
    mask = (mx <= DRAGON_V_MAX) & keep
    mask = vision._erode4(mask)
    if not mask.any() or float(mask.sum()) / max(float(keep.sum()), 1.0) > 0.6:
        return None
    for c in vision._components(mask):
        if c["n"] < DRAGON_MIN_PX:
            break
        return (float(c["cx"]), float(c["cy"]), int(c["n"]), int(c["w"]), int(c["h"]))
    return None


def break_crystal(cur, info: dict, shots: int = 3, ticks: int = 300
                  ) -> tuple[list[dict[str, Any]], str]:
    """Find an end crystal in view and destroy it: bow and arrows from where you stand,
    or a hit when it is within reach and no bow is carried."""
    bow = bool(gui.find_slots(info, "bow")) and sum(q for _, q in gui.find_slots(info, "arrow")) > 0
    weapon = None
    if bow:
        acts, err = MW._prep_item(cur, info, "bow", "break_crystal")
    else:
        weapon = ME._best_weapon(info)
        acts, err = (MW._prep_item(cur, info, weapon, "break_crystal") if weapon else ([], ""))
    if err:
        return [], err
    t = max(60, min(400, int(ticks)))
    st = {"budget": t, "used": 0, "still": 0, "miss": 0, "stage": "settle", "t": 0,
          "bow": bow, "weapon": weapon, "shots": max(1, min(8, int(shots))), "fired": 0,
          "hits": 0, "base": None, "last": None, "head": [], "gone": 0}
    acts.append(macros.marker("_crystal", st, t))
    return acts, ("break_crystal: looking for the crystal, "
                  + ("shooting it with the bow" if bow else
                     f"hitting it with the {weapon or 'hand'} (it EXPLODES: 3 blocks away "
                     f"hurts, adjacent can kill -- a bow is the safe way)"))


@macros.tick("_crystal", shrink="budget", combat=True)
def _crystal_tick(agent, st: dict[str, Any], mk_act):
    st["used"] += 1
    ME._track(agent, st)
    if ME._gate(agent, st if "label_txt" in st else {**st, "label_txt": "break_crystal"}):
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    if st["base"] is None:
        st["base"] = {"hp": ME._hp(agent), "arrows": agent._cur_inv.get("arrow", 0),
                      "bow": agent.stat_now("use_item", "bow")}
    hp = ME._hp(agent)

    def finish(why: str) -> None:
        shots = st["fired"] + st["hits"]
        hurt = (st["base"]["hp"] - hp) if (hp is not None and st["base"]["hp"] is not None) else 0
        agent.cursor_stats["crystal_runs"] = agent.cursor_stats.get("crystal_runs", 0) + 1
        agent.memory.add_note(
            f"break_crystal: {why} {shots} shot(s)/hit(s)"
            + (f", you took {hurt:.0f} damage (health {hp:.0f}/20)" if hurt > 0 else "")
            + (f". Last seen at {st['last'][0]:.0f},{st['last'][1]:.0f} px, {st['last'][2]} px "
               f"of magenta/white." if st.get("last") else "."))

    if st["used"] > st["budget"]:
        finish("budget spent --")
        return None
    hit = crystal_blob(agent._last_pov)
    if hit is None:
        st["miss"] += 1
        if st["last"] is not None and (st["fired"] or st["hits"]):
            st["gone"] += 1
            if st["gone"] >= 6:
                agent.cursor_stats["crystals_broken"] = agent.cursor_stats.get("crystals_broken", 0) + 1
                finish("CRYSTAL DESTROYED (it vanished from the view after the hit) --")
                return None
        if st["miss"] >= ME.MISS_MAX:
            agent._note_failure("break_crystal")
            agent.memory.add_note(
                "break_crystal: no magenta/white crystal in view over 26 frames (the "
                "crosshair swept up and down). Crystals sit on TOP of the obsidian towers: "
                "look up (look_abs pitch -30) toward a tower, or scan_around.")
            return None
        st["stage"] = "settle"
        return ME._sweep_step(st, mk_act)
    st["miss"], st["gone"] = 0, 0
    st["last"] = hit
    if st["stage"] == "settle":
        if int(st.get("still", 0)) >= ME.STILL_MIN:
            st["stage"] = "aim"
        else:
            return ME._still(st, mk_act())
    if st["stage"] == "aim":
        ex, ey = hit[0] - np.asarray(agent._last_pov).shape[1] / 2.0, hit[1] - np.asarray(agent._last_pov).shape[0] / 2.0
        if st["bow"]:
            ey -= max(0.0, min(5.0, 110.0 / max(float(hit[4]), 8.0))) / 0.19
        if abs(ex) > ME.AIM_TOL_X or abs(ey) > ME.AIM_TOL_Y:
            st["stage"] = "settle"
            return ME._still(st, mk_act(camera=ME._camera_toward(ex, ey)))
        st["stage"], st["t"] = ("draw" if st["bow"] else "swing"), 0
    if st["stage"] == "draw":
        st["t"] += 1
        if st["t"] <= 25:
            return ME._still(st, mk_act(use=1))
        st["stage"], st["t"] = "wait", 0
        st["fired"] += 1
        return ME._still(st, mk_act())
    if st["stage"] == "swing":
        st["hits"] += 1
        st["stage"], st["t"] = "wait", 0
        return ME._still(st, mk_act(attack=1))
    # wait: let the arrow fly / the explosion happen, then look again
    st["t"] += 1
    if st["t"] < 14:
        return ME._still(st, mk_act())
    if st["fired"] >= st["shots"] and st["bow"]:
        finish(f"{st['shots']} arrows fired and the crystal is still there --")
        return None
    if st["hits"] >= 3:
        finish("three hits and the crystal is still there (out of reach?) --")
        return None
    st["stage"] = "settle"
    return ME._still(st, mk_act())


def attack_dragon(cur, info: dict, ticks: int = 300, retreat_hp: float = 6.0,
                  weapon: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Melee the dragon while it is within reach (it perches on the central bedrock
    fountain between its flights): select the best sword, find the black mass, close
    in, pulse attack, verify on damage_dealt and kill_entity.ender_dragon."""
    weapon = weapon or ME._best_weapon(info)
    acts: list[dict[str, Any]] = []
    if weapon:
        acts, err = MW._prep_item(cur, info, weapon, "attack_dragon")
        if err:
            return [], err
    t = max(60, min(400, int(ticks)))
    st = {"budget": t, "used": 0, "still": 0, "miss": 0, "stage": "settle", "t": 0,
          "weapon": weapon, "retreat_hp": max(0.0, min(19.0, float(retreat_hp))),
          "swings": 0, "hits": 0, "dry": 0, "walked": 0, "base": None, "last": None,
          "head": [], "label_txt": "attack_dragon"}
    acts.append(macros.marker("_dragon", st, t))
    return acts, (f"attack_dragon({weapon or 'bare hands'}): up to {t} ticks, backing off "
                  f"at {st['retreat_hp']:.0f} hp")


def _dragon_detect(agent, st: dict[str, Any]):
    """The black mass by colour first (it needs no still frames and the dragon is never
    rigid: even a perched one flaps), motion as the fallback. The point to swing at is
    the LOWEST central part of the mass, not its centroid: the centroid of a dragon
    seen from below is a wing 8 blocks up (a staged scene: five swings at the
    sky), the body, legs and head are at the bottom of the silhouette."""
    hit = dragon_blob(agent._last_pov)
    if hit is None and int(st.get("still", 0)) >= ME.STILL_MIN and ME._steady(st):
        m = vision.find_moving_blob(agent._prev_pov, agent._last_pov, min_px=200)
        if m is not None:
            hit = (float(m[0]), float(m[1]), int(m[2]), int(m[3]), int(m[4]))
    if hit is None:
        return None
    x, y, n, w, h = hit
    return (x, y + h * 0.30, n, w, h)


@macros.tick("_dragon", shrink="budget", moving=True, combat=True)
def _dragon_tick(agent, st: dict[str, Any], mk_act):
    st["used"] += 1
    ME._track(agent, st)
    if ME._gate(agent, st):
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    if st["base"] is None:
        st["base"] = {"kills": ME._kills(agent), "dmg": ME._damage(agent), "hp": ME._hp(agent)}
        st["dmg_seen"] = st["base"]["dmg"]
    now = ME._damage(agent)
    if now > st["dmg_seen"]:
        st["hits"] += 1
        st["dmg_seen"] = now
    hp = ME._hp(agent)

    def finish(why: str, tail: str = "") -> None:
        dmg = (ME._damage(agent) - st["base"]["dmg"]) / 10.0
        hp0 = st["base"]["hp"]
        agent.cursor_stats["dragon_runs"] = agent.cursor_stats.get("dragon_runs", 0) + 1
        agent.cursor_stats["dragon_hits"] = agent.cursor_stats.get("dragon_hits", 0) + st["hits"]
        agent.memory.add_note(
            f"attack_dragon: {why} {st['swings']} swings, {st['hits']} landed, {dmg:.1f} hp "
            f"of damage dealt"
            + (f", you took {hp0 - hp:.0f} (health {hp:.0f}/20)"
               if hp is not None and hp0 is not None and hp0 - hp > 0 else "")
            + (f". Last seen: a {st['last'][3]}x{st['last'][4]} px black mass." if st.get("last") else ".")
            + (" " + tail if tail else ""))

    killed = [k for k in ME._new_kills(agent, st["base"]["kills"])]
    if any("dragon" in k for k in killed):
        finish("THE DRAGON IS DEAD.", "The exit portal at the centre takes you home.")
        return None
    if st["stage"] != "back" and hp is not None and hp <= st["retreat_hp"]:
        st["stage"], st["t"] = "back", 0
    if st["used"] > st["budget"] and st["stage"] != "back":
        finish("budget spent, the dragon lives.",
               "It heals from every crystal still standing (break_crystal); hit its HEAD "
               "when it perches (the body takes a quarter of the damage); call again.")
        return None
    if st["stage"] == "back":
        st["t"] += 1
        if st["t"] <= ME.RETREAT_TICKS:
            return ME._still(st, mk_act(back=1, sprint=1))
        finish(f"BROKE OFF at {hp:.0f}/20 health.", "Eat, then come back.")
        return None
    if st["stage"] == "settle":
        if int(st.get("still", 0)) >= 1:
            st["stage"] = "aim"
        else:
            return ME._still(st, mk_act())
    if st["stage"] == "aim":
        hit = _dragon_detect(agent, st)
        if hit is None:
            st["miss"] += 1
            if st["miss"] >= ME.MISS_MAX:
                if st["hits"]:
                    finish("the dragon is out of view.", "It flies; wait for the perch.")
                else:
                    agent._note_failure("attack_dragon")
                    agent.memory.add_note(
                        "attack_dragon: no black mass in view over 26 frames (the crosshair "
                        "swept up and down). The dragon circles the towers and perches on "
                        "the bedrock fountain at the centre every minute or so: stand near "
                        "the fountain, scan_around, and call again when it lands.")
                return None
            st["stage"] = "settle"
            return ME._sweep_step(st, mk_act)
        st["miss"] = 0
        st["last"] = hit
        fh, fw = np.asarray(agent._last_pov).shape[0], np.asarray(agent._last_pov).shape[1]
        ex, ey = hit[0] - fw / 2.0, hit[1] - fh / 2.0
        # The hitbox is many blocks wide: a loose tolerance, and no settling between
        # aim steps (the silhouette moves every tick, a strict loop never converged).
        if abs(ex) > ME.AIM_TOL_X * 3 or abs(ey) > ME.AIM_TOL_Y * 3:
            return ME._still(st, mk_act(camera=ME._camera_toward(ex, ey)))
        # A mass that fills less than a fifth of the view is far: walk in first.
        far = hit[2] < 0.12 * fw * fh * 0.82
        st["stage"], st["t"] = ("walk" if (st["dry"] >= 2 or far) else "swing"), 0
    if st["stage"] == "walk":
        st["t"] += 1
        st["walked"] += 1
        if st["t"] <= ME.WALK_TICKS and st["walked"] <= 120:
            return ME._still(st, mk_act(forward=1, sprint=1))
        st["dry"], st["stage"] = 0, "settle"
        return ME._still(st, mk_act())
    if st["stage"] == "swing":
        st["swings"] += 1
        st["landed_at"] = st["dmg_seen"]
        st["stage"], st["t"] = "recover", 0
        return ME._still(st, mk_act(attack=1))
    st["t"] += 1
    if st["t"] < ME.RECOVER:
        return ME._still(st, mk_act())
    if st["dmg_seen"] > st.get("landed_at", st["dmg_seen"]):
        st["dry"] = 0
    else:
        st["dry"] += 1
    st["stage"] = "settle"
    return ME._still(st, mk_act())


# -- registration -----------------------------------------------------------------------------

def register_all(register, Procedure) -> None:
    register(Procedure(
        "throw_eye",
        "Throw an eye of ender and WATCH it: reports the yaw it flew toward (the "
        "stronghold's bearing) and whether it climbed (far) or dropped (the stronghold is "
        "below you). Each throw uses the eye up (it does not drop back here).",
        throw_eye, needs_cursor=True, needs_info=True,
        preconditions="Stand in the open with a clear view ahead (the eye flies up to 12 "
                      "blocks); ender_eye carried; no screen open.",
        params={"fetch": "true to walk out along the bearing looking for a dropped eye "
                         "(default false)"}))
    register(Procedure(
        "travel_bearing",
        "Walk `blocks` along the world heading `yaw` in closed-loop legs (jumping small "
        "rises), and say how far you got; stops early at a wall, a drop or lava.",
        travel_bearing, needs_cursor=True, needs_info=True,
        preconditions="Overland walking; long trips are several calls.",
        params={"yaw": "heading in degrees (from throw_eye)", "blocks": "distance (2-400)"}))
    register(Procedure(
        "fill_end_portal",
        "Put an eye of ender into every empty frame of the End portal: the 12 frames stand "
        "around a 3x3 pit; (x, y, z) is the pit's middle cell at the FRAMES' level. Walks "
        "around the ring outside it, clicks each frame's outer face with an eye, verifies "
        "each on the eye count; a frame that refuses already holds one. Resumable.",
        fill_end_portal, needs_cursor=True, needs_info=True,
        preconditions="Standing in the portal room, 1-12 ender_eye carried (one per empty "
                      "frame), no screen open.",
        params={"x": "pit centre x", "y": "frame level y", "z": "pit centre z"}))
    register(Procedure(
        "enter_end",
        "Jump into the activated End portal (the pit centred on x, y, z) and wait for the "
        "teleport; reports the End and where the island lies.",
        enter_end, needs_cursor=True, needs_info=True,
        preconditions="All 12 frames hold an eye (the pit shows the black starry portal).",
        params={"x": "pit centre x", "y": "frame level y", "z": "pit centre z"}))
    register(Procedure(
        "mine_end_stone",
        "Dig the pale End ground with a pickaxe until an end_stone is picked up: aims at "
        "pitch `pitch` toward the island (x 0, z 0) or the given `yaw`.",
        mine_end_stone, needs_cursor=True, needs_info=True,
        preconditions="In the End, a pickaxe carried, end stone within reach in that "
                      "direction (the spawn platform itself is obsidian).",
        params={"yaw": "heading (optional, default toward the island)",
                "pitch": "camera pitch, + is down (default 30)", "ticks": "budget (default 240)"}))
    register(Procedure(
        "break_crystal",
        "Destroy the end crystal in view (the bright magenta/white cube on top of an "
        "obsidian tower): draws and shoots the bow at it up to `shots` times, or hits it "
        "when no bow is carried (it explodes -- keep 3+ blocks away). Verified by the "
        "crystal vanishing from the view.",
        break_crystal, needs_cursor=True, needs_info=True,
        preconditions="The crystal in view (look up at a tower); bow + arrows for safety.",
        params={"shots": "arrows to spend (default 3)", "ticks": "budget (default 300)"}))
    register(Procedure(
        "attack_dragon",
        "Melee the ender dragon while it is in reach -- it perches on the bedrock fountain "
        "at the island's centre between flights: finds the black mass, closes in, pulses "
        "the sword, backs off at `retreat_hp`. Verified on damage_dealt / kill_entity.",
        attack_dragon, needs_cursor=True, needs_info=True,
        preconditions="Crystals broken first (they heal it); stand by the fountain when "
                      "it lands; a sword carried.",
        params={"ticks": "budget (60-400)", "retreat_hp": "health to back off at (default 6)",
                "weapon": "item to hold (optional)"}))
