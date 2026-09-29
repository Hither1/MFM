"""Entities: find one in the frame, face it, fight it, shoot it, right-click it, ride it.

Why. A quarter of the task suite is an entity the agent cannot see in any observation
channel: "combat and kill zombies/skeletons/spiders/witch/enderman/wolves", "hunt pigs
with a sword", "hunt a horse with a bow or sword", "shoot a phantom with a bow", "use
bow as your weapon", "defend yourself using a shield", "shear sheep to collect wool",
"use lead to get animals", "hook a chicken using a fishing rod", "trap a spider with a
boat", "explore with a boat", and the dragon chain's blaze rod and ender pearl.
`info['mobs']` is ALWAYS empty here (the `mobs` action region is never set, and the
evaluation forwards no entity channel), so there is no coordinate to aim at the way
`macros_world` aims at a block face. Everything in this module is therefore vision
(`vision.find_moving_blob` for the blob, `vision.entity_hint` for the label) closing a
loop that is VERIFIED on statistics: `use_item.<weapon>` counts the swings that landed,
`custom.damage_dealt` the tenths of hp taken off, `kill_entity.<mob>` the kill, the
inventory the wool/milk/lead, and the position the boat you boarded.

The measured facts this is built on (standalone sim):
- attack must be PULSED. Held 60 ticks it hits nothing; 1 tick on / 9 off with a
  diamond sword on a zombie at 2 blocks gives `use_item.diamond_sword +4` (four
  landed swings), `custom.damage_dealt +201`, `kill_entity.zombie +1`.
- melee reach is ~3 blocks and the crosshair must sit on the mob's BODY, not its head
  (a pig's hitbox is 0.9 blocks high; aiming at its head from 3 blocks missed).
- a bow needs `use` held >= 25 ticks before the release; the arrow leaves on the
  release tick and shows up as `use_item.bow +1`, arrow -1.
- a boat: `use` on water places it (`use_item.oak_boat +1`), `use` on the boat boards
  it (the position jumps into it, y -0.45), `forward` drives it, `sneak` gets out.

- a shield in the MAIN hand, raised by holding `use`, is worth four fifths of the
  damage: 100 ticks blocking a zombie at 1.6 blocks cost 2.5 hp against 12.5 for the
  SAME zombie over the next 100 ticks with the shield down (custom.damage_taken, which
  is the honest meter here -- the health bar also regenerates).
- the horizontal field of view is ~100 degrees: a zombie summoned exactly 40 degrees
  off the facing renders 225 px right of the crosshair in a 640-wide frame. That is
  4.7 px per degree near the centre, and it is what sets the aim gains below.

The loop shape every macro here shares. A pixel difference is only meaningful between
two frames taken with the camera still, so each tick records whether the action it
returned left the view alone (`_still`), and detection only runs after two still ticks
in a row. Motion is tried first because it needs no per-mob knowledge; the colour
classifier answers when motion finds nothing. When NEITHER finds anything the crosshair
sweeps 21 degrees down and back up before the macro gives up -- a pig two blocks away
renders below the middle of the view and, at 2.5 blocks, under the HUD line, and stage
s4's first run could not see a sheep it was standing next to.

Detector accuracy, measured on the staged-scene calibration corpus (15 frames, one mob each
at 2.5-8 blocks, on a stone platform against a FOREST horizon -- the cluttered case,
not a swept arena):
  * `entity_hint(frame, want=<mob>)`, the normal call, puts its blob on the mob in
    13 of 15. The two misses are structural, not tuning: a skeleton's bone renders at
    the same 96-135 grey as the stone it stands on, and a phantom is the same blue-grey
    as the sky it flies against. Both are motion-only.
  * the OPEN scan (no label) puts its blob on the mob in 14 of 15 -- which is what
    aiming needs -- but names the right mob in only 7 of 15, because three mobs and the
    stone floor share one neutral-grey band. Pass a label when the task text names one.
  * shearing a sheep drops the wool ON THE GROUND. Nothing this module can read moves:
    not the inventory, not use_item. `use_on_entity(shears)` therefore reports a
    failure it did not have, and the plan is `use_on_entity(shears)` then
    `collect_drops` (measured in a staged scene: the sheep in the frame was bare and the
    wool block was lying two blocks away).
  * a DROPPED ITEM bobs and spins on the ground and is a real 132 px moving blob. If a
    fight ends and something small and low is still "moving" where the mob died, that
    is its drop: collect_drops, do not swing at it.
  * `find_moving_blob` finds a live mob (a wandering pig 3 blocks off: a 95-103 px
    blob) and finds nothing on an empty platform or after the mob is killed. With AI
    DISABLED 11 of the 15 corpus mobs still animated enough to be seen, but four --
    a zombie and a pig at 3 blocks, a skeleton, a cow -- were perfectly rigid, zero
    changed pixels. That is why the colour path exists: a stage prepares exactly those
    frozen mobs, and only colour can see them.
"""
from __future__ import annotations

import math
from typing import Any

from mcu_worldmodel import gui, macros
from mcu_worldmodel import macros_world as MW

#: Crosshair tolerance in pixels before a swing / a right-click. Sized against the
#: HITBOX, not against zero: a zombie is 0.6 blocks wide, so at the 3-block melee reach
#: its half-width is 5.7 degrees = 27 px, and an animal is wider still. The first cut
#: (14/12 px) was tighter than the target and cost iterations the budget needed --
#: a staged scene got one right-click into a 200-tick shear because the loop kept refining an
#: aim that was already on the sheep.
AIM_TOL_X, AIM_TOL_Y = 18.0, 16.0
#: Pixels -> degrees per tick. The horizontal field of view was MEASURED at ~100
#: degrees (a staged scene: a zombie summoned exactly 40 degrees off the facing rendered
#: 225 px right of the crosshair, and a pinhole projection puts tan(50 deg) at half
#: the frame), which is 4.7 px per degree near the centre, i.e. 0.213 degrees per
#: pixel on both axes (the pixels are square). The gain is 75% of that: it converges
#: from the edge of the view in four steps and never overshoots.
GAIN_PITCH, GAIN_YAW = 0.16, 0.16
CAM_MAX = 22.0
#: Detection attempts with nothing found before a macro gives up and says so.
MISS_MAX = 26
#: Pitch steps (degrees, + is down) walked while nothing is detected. A mob is often
#: simply BELOW the middle of the view: an eye sits 1.62 blocks up and a pig's hitbox
#: is 0.9 high, so a pig two blocks away renders under the crosshair and, at 2.5
#: blocks, under the HUD line -- a staged scene could not see a sheep it was standing
#: next to. The sequence sums to zero, so a macro that finds nothing leaves the camera
#: where it found it, and it spans 21 degrees down and 21 up.
SWEEP = (7.0, 7.0, 7.0, 0.0, -7.0, -7.0, -7.0, -7.0, -7.0, -7.0, 0.0, 7.0, 7.0, 7.0, 0.0)
#: Ticks with nothing pressed AND an unchanged measured heading before a pixel diff is
#: trusted. Three, not two: the rendered frame lags the avatar's state by one tick, so
#: the first frame after a turn still shows the old view even though [STATE] already
#: reports the new yaw. With two, a staged scene kept finding the tree line sliding in from
#: the right after every aim step, turned toward it, and span in a circle -- a whole
#: 300-tick fight budget, 100 aim steps, the error stuck at +268 px.
STILL_MIN = 3
#: Melee cadence: swing, then recover. A sword's full-damage cooldown is ~12 ticks and
#: the whole settle/aim/recover cycle is ~11-13, so every swing lands at full damage.
RECOVER = 8
#: Sprint ticks per closing step when swings are not landing (~1.1 blocks).
WALK_TICKS = 6
#: Retreat: back away this many ticks (~3 blocks) when health falls to `retreat_hp`.
RETREAT_TICKS = 26
#: Weapons `fight` picks from when the model does not name one, best first. Damage
#: order, then the tools that still hit harder than a fist.
WEAPONS = ("netherite_sword", "diamond_sword", "iron_sword", "stone_sword",
           "golden_sword", "wooden_sword", "trident", "netherite_axe", "diamond_axe",
           "iron_axe", "stone_axe", "golden_axe", "wooden_axe", "netherite_pickaxe",
           "diamond_pickaxe", "iron_pickaxe", "stone_pickaxe", "wooden_pickaxe")
#: Keys whose press changes what the next frame shows (so no pixel diff is meaningful).
_MOVES = ("forward", "back", "left", "right", "jump", "sprint", "attack", "use",
          "sneak", "inventory")
#: Colour detectors a macro can name in its marker (`detect=<key>`) in place of
#: `vision.entity_hint(want=label)`: `fn(frame, near=(x, y)) -> (label, x, y, n, w, h)`
#: or None. A blaze in the Nether needs one -- its yellow is also lava's -- and
#: `macros_nether` registers `vision_nether.blaze_hint` under "blaze".
DETECTORS: dict[str, Any] = {}


# -- state shared by every marker here ------------------------------------------

def _still(st: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Return `action`, having recorded whether it leaves the view unchanged.

    The whole motion detector rests on this counter: one degree of camera moves every
    pixel in the frame, and a diff taken across it reports the world as one huge blob.
    """
    cam = action.get("camera") or [0.0, 0.0]
    moved = (abs(float(cam[0])) > 1e-6 or abs(float(cam[1])) > 1e-6
             or any(action.get(k) for k in _MOVES))
    st["still"] = 0 if moved else int(st.get("still", 0)) + 1
    return action


def _track(agent, st: dict[str, Any]) -> None:
    """Record the measured heading for this tick.

    `_still` says what the macro PRESSED; this says what the engine did. They disagree
    by one tick: a camera action applied at tick N is still settling in the frame
    observed after tick N+1, so two "still" ticks after a turn can still bracket a
    moving view. A staged scene spent a whole 300-tick fight budget on that -- the diff
    kept finding the tree line sliding in from the right, the aim turned toward it, and
    the loop span in a circle reporting a 268 px error after 100 aim steps. The pitch
    and yaw in [STATE] are exact, so the gate is: the two frames were taken at the SAME
    measured heading.
    """
    pos = agent._cur_pos
    h = (round(float(pos["yaw"]), 3), round(float(pos["pitch"]), 3)) if pos else None
    st["head"] = ((st.get("head") or [])[-(STILL_MIN - 1):] + [h])


def _steady(st: dict[str, Any]) -> bool:
    h = st.get("head") or []
    return (len(h) >= STILL_MIN and h[0] is not None
            and all(v == h[0] for v in h[-STILL_MIN:]))


def _detect(agent, st: dict[str, Any]) -> tuple[int, int, int, int, int, str] | None:
    """(x, y, n_px, w, h, how) of the entity in view, or None.

    Motion first (it needs no per-mob knowledge, so it finds a horse, a witch and a
    phantom with one code path), colour second (it is the only thing that sees a rigid
    NoAI mob, and it is what turns a blob into the label a note can name).
    """
    from mcu_worldmodel import vision

    hit = None
    # A registered detector (by `detect=` or by the label) goes FIRST: a mob with a
    # dedicated detector is one whose own particles fool the motion path -- an
    # enderman's purple motes and a blaze's smoke are real moving blobs beside the
    # body (a staged scene: a fight aimed at the motes for 96 steps, +303 px off the
    # enderman standing centred in the view).
    custom = DETECTORS.get(str(st.get("detect") or "")) or DETECTORS.get(
        str(st.get("label") or ""))
    if custom is not None and agent._last_pov is not None:
        c = custom(agent._last_pov, near=st.get("last_xy"))
        if c is not None:
            st["seen_colour"] = int(st.get("seen_colour", 0)) + 1
            hit = (c[1], c[2], c[3], c[4], c[5], c[0])
    if hit is None and int(st.get("still", 0)) >= STILL_MIN and _steady(st):
        m = vision.find_moving_blob(agent._prev_pov, agent._last_pov)
        if m is not None:
            st["seen_motion"] = int(st.get("seen_motion", 0)) + 1
            hit = (m[0], m[1], m[2], m[3], m[4], "motion")
    if hit is None:
        # a detector that misses (a dark corridor, a night sky) must not disable the
        # generic band: audit pass 14 reproduced enderman_hint None / entity_hint hit
        # on dim frames, and the fallback was skipped whenever a detector existed
        # `near`: keep tracking the SAME mob across ticks. Without it a loop steering
        # on the best blob in each frame can be walked to a different candidate that
        # scores higher for one frame (the bug `find_tree_trunk`'s prefer_x fixed).
        c = vision.entity_hint(agent._last_pov, want=st.get("label") or None,
                               near=st.get("last_xy"))
        if c is not None:
            st["seen_colour"] = int(st.get("seen_colour", 0)) + 1
            hit = (c[1], c[2], c[3], c[4], c[5], c[0])
    if hit is not None:
        st["last_xy"] = (float(hit[0]), float(hit[1]))
        st["sweep"] = 0
    return hit


def _sweep_step(st: dict[str, Any], mk_act) -> dict[str, Any]:
    """One tick of the up-and-down look a macro does while it sees nothing.

    One pitch step, then STILL_MIN still ticks. Without them the sweep would
    disable the motion detector for its whole duration -- and motion is the only thing
    that sees a skeleton (bone grey on stone grey) or a phantom (blue-grey on sky).
    """
    i = int(st.get("sweep", 0))
    st["sweep"] = i + 1
    if i % (STILL_MIN + 1) == 0:
        dp = SWEEP[(i // (STILL_MIN + 1)) % len(SWEEP)]
        if dp:
            return _still(st, mk_act(camera=[dp, 0.0]))
    return _still(st, mk_act())


def _aim_error(agent, hit) -> tuple[float, float]:
    """(dx, dy) in pixels from the crosshair to the point to aim at.

    That point is the blob's centroid, EXCEPT when the blob runs into the HUD line:
    the searched region stops at 0.82 of the frame and a short animal close by carries
    on below it, so the visible centroid sits above the real hitbox centre and a swing
    aimed there goes over its back. A pig 2.5 blocks away is half under the hotbar.
    """
    frame = agent._last_pov
    h, w = (frame.shape[0], frame.shape[1]) if frame is not None else (360, 640)
    cy, bh = float(hit[1]), float(hit[4])
    bottom = cy + bh / 2.0
    # Only for a SMALL blob, and never by much: a big one that reaches the HUD line is
    # something filling the view (a boat at your feet is 288x247 px and centred), and
    # correcting it aimed 74 px below the hull -- a staged scene spent a whole budget on that.
    if bottom >= h * 0.82 - 3.0 and bh <= h * 0.35:
        cy += min(25.0, (bottom - cy) * 0.6)
    return (float(hit[0]) - w / 2.0, cy - h / 2.0)


def _camera_toward(ex: float, ey: float, bias_pitch: float = 0.0) -> list[float]:
    dp = max(-CAM_MAX, min(CAM_MAX, ey * GAIN_PITCH + bias_pitch))
    dy = max(-CAM_MAX, min(CAM_MAX, ex * GAIN_YAW))
    return [dp, dy]


def _hp(agent) -> float | None:
    v = getattr(agent, "_last_health", None)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _kills(agent) -> dict[str, float]:
    """The whole kill_entity bucket as floats -- a fight does not know in advance which
    mob it is swinging at, so the kill is detected by ANY bucket entry rising."""
    raw = (agent.ledger._prev or {}).get("kill_entity")
    if not isinstance(raw, dict):
        return {}
    return {str(k): (float(v.item()) if hasattr(v, "item") else float(v))
            for k, v in raw.items()}


def _new_kills(agent, base: dict[str, float]) -> list[str]:
    return [k for k, v in _kills(agent).items() if v > base.get(k, 0.0)]


def _damage(agent) -> float:
    """Tenths of hp this episode has taken off entities (custom.damage_dealt)."""
    return agent.stat_now("custom", "damage_dealt")


def _inv_delta(agent, base: dict[str, int]) -> dict[str, int]:
    return {k: agent._cur_inv.get(k, 0) - base.get(k, 0)
            for k in set(agent._cur_inv) | set(base)
            if agent._cur_inv.get(k, 0) != base.get(k, 0)}


def _dist(a, b) -> float:
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))


def _no_entity_note(st: dict[str, Any], what: str) -> str:
    want = st.get("label")
    return (f"{st['label_txt']}: {what} -- nothing moved in view over {MISS_MAX} still "
            f"frames" + (f" and no {want}-coloured blob was found" if want else
                         " and no mob colour was recognised")
            + " (the crosshair swept 21 degrees up and down while looking). Nothing is "
              "in front of you, or the mob is behind you: scan_around, then turn toward "
              "the heading its tile shows and call this again.")


def _gate(agent, st: dict[str, Any]) -> bool:
    """False (and the plan is dropped) when a screen is open: a world click would go
    into the GUI instead of at the mob."""
    if agent._gui_open:
        agent._flush_tail(f"{st['label_txt']}: a screen is open; the swing/click would "
                          f"go into the GUI. close_inventory first.", "entity_gui_flush")
        return True
    return False


def _best_weapon(info: dict) -> str | None:
    for w in WEAPONS:
        if gui.find_slots(info, w):
            return w
    return None


# -- face_entity ----------------------------------------------------------------

def face_entity(cur, info: dict, ticks: int = 60, label: str | None = None,
                detect: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Steer the crosshair onto the nearest moving/coloured entity."""
    t = max(10, min(200, int(ticks)))
    st = {"budget": t, "used": 0, "still": 0, "miss": 0, "label": (label or None),
          "label_txt": f"face_entity({label or 'any'})", "detect": (detect or None)}
    return [macros.marker("_face", st, t)], (
        f"face_entity: centring the crosshair on "
        f"{('a ' + label) if label else 'whatever moves'} (up to {t} ticks)")


@macros.tick("_face", shrink="budget", combat=True)
def _face_tick(agent, st: dict[str, Any], mk_act):
    _track(agent, st)
    if _gate(agent, st):
        return None
    st["used"] += 1
    if st["used"] > st["budget"]:
        agent._note_failure("face_entity")
        agent.memory.add_note(
            f"{st['label_txt']}: {st['budget']} ticks spent without centring"
            + (f" (last seen {st['last'][5]} at {st['last'][0]},{st['last'][1]})"
               if st.get("last") else " and nothing was ever detected")
            + ". Call it again, or scan_around first.")
        return None
    hit = _detect(agent, st)
    if hit is None:
        st["miss"] += 1
        if st["miss"] >= MISS_MAX:
            agent._note_failure("face_entity")
            agent.memory.add_note(_no_entity_note(st, "no entity in view"))
            return None
        return _sweep_step(st, mk_act)
    st["miss"] = 0
    st["last"] = hit
    ex, ey = _aim_error(agent, hit)
    if abs(ex) <= AIM_TOL_X and abs(ey) <= AIM_TOL_Y:
        agent.cursor_stats["face_entity_ok"] = (
            agent.cursor_stats.get("face_entity_ok", 0) + 1)
        pos = agent._cur_pos or {}
        agent.memory.add_note(
            f"{st['label_txt']}: crosshair centred on a {hit[5]} blob ({hit[2]} px, "
            f"{hit[3]}x{hit[4]}), {abs(ex):.0f}/{abs(ey):.0f} px off"
            + (f", facing yaw {pos.get('yaw', 0):.0f} pitch {pos.get('pitch', 0):.0f}"
               if pos else "")
            + ". It is in front of you now: fight, shoot_bow or use_on_entity.")
        return None
    return _still(st, mk_act(camera=_camera_toward(ex, ey)))


# -- fight ------------------------------------------------------------------------

def fight(cur, info: dict, ticks: int = 300, retreat_hp: float = 6.0,
          weapon: str | None = None, label: str | None = None,
          detect: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Melee an entity: select a weapon, face it, close, pulse attack, verify the kill."""
    weapon = weapon or _best_weapon(info)
    txt = f"fight({weapon or 'bare hands'})"
    acts: list[dict[str, Any]] = []
    if weapon:
        acts, err = MW._prep_item(cur, info, weapon, txt)
        if err:
            return [], err
    t = max(40, min(400, int(ticks)))
    st = {"budget": t, "used": 0, "still": 0, "miss": 0, "stage": "settle", "t": 0,
          "weapon": weapon, "label": (label or None), "label_txt": txt,
          "detect": (detect or None),
          "retreat_hp": max(0.0, min(19.0, float(retreat_hp))),
          "swings": 0, "hits": 0, "dry": 0, "walked": 0, "walk_needed": False,
          "landed": False,
          "strafe": 1, "base": None}
    acts.append(macros.marker("_fight", st, t))
    return acts, (f"{txt}: up to {t} ticks, backing off at {st['retreat_hp']:.0f} hp"
                  + (f", looking for a {label}" if label else ""))


def _fight_finish(agent, ft: dict[str, Any], why: str, tail: str = "") -> None:
    hits = ft["hits"]
    dmg = (_damage(agent) - ft["base"]["dmg"]) / 10.0
    hp = _hp(agent)
    hp0 = ft["base"]["hp"]
    weapon = ft["weapon"]
    stat_hits = ((agent.stat_now("use_item", weapon) - ft["base"]["use"])
                 if weapon else None)
    agent.cursor_stats["fight_runs"] = agent.cursor_stats.get("fight_runs", 0) + 1
    agent.cursor_stats["fight_hits"] = agent.cursor_stats.get("fight_hits", 0) + hits
    agent.memory.add_note(
        f"{ft['label_txt']}: {why} {ft['swings']} swings, {hits} landed"
        + (f" (use_item.{weapon} +{stat_hits:g})" if stat_hits else "")
        + f", {dmg:.1f} hp of damage dealt"
        + (f", you took {hp0 - hp:.0f} (health {hp:.0f}/20)"
           if hp is not None and hp0 is not None and hp0 - hp > 0 else
           (f", health {hp:.0f}/20 unchanged" if hp is not None else ""))
        + (f", walked {ft['walked']} ticks closing in" if ft["walked"] else "")
        + (f". Last seen: a {ft['last'][5]} blob {ft['last'][3]}x{ft['last'][4]} px, "
           f"crosshair {ft['err'][0]:+d}/{ft['err'][1]:+d} px off it after "
           f"{ft.get('aims', 0)} aim steps" if ft.get("last") and ft.get("err") else "")
        + "." + (" " + tail if tail else ""))


@macros.tick("_fight", shrink="budget", moving=True, combat=True)
def _fight_tick(agent, ft: dict[str, Any], mk_act):
    ft["used"] = int(ft.get("used", 0)) + 1
    _track(agent, ft)
    return _fight_step(agent, ft, mk_act)


def _fight_step(agent, ft: dict[str, Any], mk_act):
    if _gate(agent, ft):
        return None
    if ft["base"] is None:
        ft["base"] = {"kills": _kills(agent), "dmg": _damage(agent), "hp": _hp(agent),
                      "use": (agent.stat_now("use_item", ft["weapon"])
                              if ft["weapon"] else 0.0)}
        ft["dmg_seen"] = ft["base"]["dmg"]
    # Read the damage ledger EVERY tick, not only at the end of a recover window: the
    # swing that kills lands on the same tick the kill registers, and a counter that
    # only looked during recover reported "3 landed" for four landed swings.
    now = _damage(agent)
    if now > ft["dmg_seen"]:
        ft["hits"] += 1
        ft["dmg_seen"] = now
        ft["landed"] = True

    killed = _new_kills(agent, ft["base"]["kills"])
    if killed:
        _fight_finish(agent, ft, f"KILLED {', '.join(sorted(killed))}.",
                      "Sweep the drops with collect_drops if it dropped anything.")
        return None
    hp = _hp(agent)
    if ft["stage"] != "back" and hp is not None and hp <= ft["retreat_hp"]:
        ft["stage"], ft["t"] = "back", 0
    if ft["used"] > ft["budget"] and ft["stage"] != "back":
        _fight_finish(agent, ft, "budget spent, no kill.",
                      "It is still alive: call fight again (it is in front of you), or "
                      "back off and heal first.")
        return None

    if ft["stage"] == "back":
        ft["t"] += 1
        if ft["t"] <= RETREAT_TICKS:
            return _still(ft, mk_act(back=1, sprint=1))
        _fight_finish(
            agent, ft, f"BROKE OFF at {hp:.0f}/20 health (retreat_hp "
                       f"{ft['retreat_hp']:.0f}) and backed away ~3 blocks.",
            "Eat, pillar_up out of reach, or come back with a shield; do NOT walk back "
            "into it at this health.")
        return None

    if ft["stage"] == "settle":
        if int(ft.get("still", 0)) >= STILL_MIN:
            ft["stage"] = "aim"
            return _fight_step(agent, ft, mk_act)
        return _still(ft, mk_act())

    if ft["stage"] == "aim":
        hit = _detect(agent, ft)
        if hit is None:
            ft["miss"] += 1
            if ft["miss"] >= MISS_MAX:
                if ft["hits"]:
                    _fight_finish(agent, ft, "the target is gone from view.",
                                  "It may have died out of sight or run off; check the "
                                  "kill list in [STATE] and collect_drops.")
                else:
                    agent._note_failure("fight")
                    agent.memory.add_note(_no_entity_note(ft, "nothing to fight"))
                return None
            ft["stage"] = "settle"
            return _sweep_step(ft, mk_act)
        ft["miss"] = 0
        ft["last"] = hit
        ex, ey = _aim_error(agent, hit)
        ft["aims"] = int(ft.get("aims", 0)) + 1
        ft["err"] = (round(ex), round(ey))
        if abs(ex) > AIM_TOL_X or abs(ey) > AIM_TOL_Y:
            ft["stage"] = "settle"
            return _still(ft, mk_act(camera=_camera_toward(ex, ey)))
        ft["stage"], ft["t"] = ("walk" if ft["walk_needed"] else "swing"), 0
        return _fight_step(agent, ft, mk_act)

    if ft["stage"] == "walk":
        ft["t"] += 1
        ft["walked"] += 1
        if ft["t"] <= WALK_TICKS and ft["walked"] <= 150:
            return _still(ft, mk_act(forward=1, sprint=1))
        ft["walk_needed"], ft["dry"], ft["stage"] = False, 0, "settle"
        return _still(ft, mk_act())

    if ft["stage"] == "swing":
        ft["swings"] += 1
        ft["landed"] = False
        ft["stage"], ft["t"] = "recover", 0
        return _still(ft, mk_act(attack=1))

    # recover: let the cooldown run, read the damage ledger, then look again.
    ft["t"] += 1
    if ft["t"] < RECOVER:
        hurt = (ft["base"]["hp"] is not None and hp is not None
                and hp < ft["base"]["hp"])
        if ft["t"] == 2 and hurt:
            # One sidestep per swing while something is actually hitting back: enough
            # to spoil a skeleton's aim without walking out of melee reach.
            ft["strafe"] = -ft["strafe"]
            return _still(ft, mk_act(**{"left" if ft["strafe"] > 0 else "right": 1}))
        return _still(ft, mk_act())
    if ft.get("landed"):
        ft["dry"] = 0
    else:
        ft["dry"] += 1
        if ft["dry"] >= 2:
            # Two swings in a row took nothing off it: it is out of the ~3-block
            # entity reach, so close in rather than keep swinging at air.
            ft["walk_needed"] = True
    ft["stage"] = "settle"
    return _still(ft, mk_act())


# -- shoot_bow ---------------------------------------------------------------------

def shoot_bow(cur, info: dict, shots: int = 3, draw: int = 25,
              label: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Face the target, draw the bow, release; `shots` times, verified on the arrows."""
    txt = "shoot_bow"
    if not gui.find_slots(info, "bow"):
        return [], "shoot_bow: you carry no bow."
    arrows = sum(q for _, q in gui.find_slots(info, "arrow"))
    if arrows <= 0:
        return [], "shoot_bow: you carry no arrows (a bow without arrows fires nothing)."
    acts, err = MW._prep_item(cur, info, "bow", txt)
    if err:
        return [], err
    n = max(1, min(10, int(shots)))
    d = max(25, min(60, int(draw)))
    st = {"shots": n, "draw": d, "fired": 0, "used": 0, "still": 0, "miss": 0,
          "stage": "settle", "t": 0, "label": (label or None), "label_txt": txt,
          "budget": n * (d + 44) + 60, "base": None, "aimed": 0}
    acts.append(macros.marker("_shoot", st, st["budget"]))
    return acts, (f"shoot_bow: {n} arrow(s) at {d}-tick draws, {arrows} carried"
                  + (f", looking for a {label}" if label else ""))


def _shoot_finish(agent, sh: dict[str, Any], why: str) -> None:
    used = agent.stat_now("use_item", "bow") - sh["base"]["bow"]
    arrows = agent._cur_inv.get("arrow", 0) - sh["base"]["arrows"]
    dmg = (_damage(agent) - sh["base"]["dmg"]) / 10.0
    killed = _new_kills(agent, sh["base"]["kills"])
    agent.cursor_stats["shoot_bow_shots"] = (
        agent.cursor_stats.get("shoot_bow_shots", 0) + int(used))
    agent.memory.add_note(
        f"shoot_bow: {why} {used:g} arrow(s) left the bow (use_item.bow), "
        f"arrows {arrows:+d}, {dmg:.1f} hp of damage dealt"
        + (f", KILLED {', '.join(sorted(killed))}" if killed else "")
        + ". " + ("Arrows drop over distance -- past ~10 blocks aim a little above the "
                  "target." if not killed and dmg <= 0 else
                  "Sweep the drops with collect_drops." if killed else
                  "It is hit but alive: shoot again or close in with fight."))


@macros.tick("_shoot", shrink="budget", combat=True)
def _shoot_tick(agent, sh: dict[str, Any], mk_act):
    sh["used"] = int(sh.get("used", 0)) + 1
    _track(agent, sh)
    return _shoot_step(agent, sh, mk_act)


def _shoot_step(agent, sh: dict[str, Any], mk_act):
    if _gate(agent, sh):
        return None
    if sh["base"] is None:
        sh["base"] = {"bow": agent.stat_now("use_item", "bow"),
                      "arrows": agent._cur_inv.get("arrow", 0),
                      "dmg": _damage(agent), "kills": _kills(agent)}
    if sh["used"] > sh["budget"]:
        _shoot_finish(agent, sh, "budget spent --")
        return None
    if sh["fired"] >= sh["shots"]:
        if sh["t"] < 8:                      # let the statistic catch up
            sh["t"] += 1
            return _still(sh, mk_act())
        _shoot_finish(agent, sh, f"{sh['fired']} shot(s) fired --")
        return None

    if sh["stage"] == "settle":
        if int(sh.get("still", 0)) >= STILL_MIN or sh["aimed"] > 24:
            sh["stage"] = "aim"
            return _shoot_step(agent, sh, mk_act)
        return _still(sh, mk_act())

    if sh["stage"] == "aim":
        sh["aimed"] += 1
        hit = _detect(agent, sh)
        if hit is None:
            sh["miss"] += 1
            if sh["miss"] >= MISS_MAX:
                if sh["fired"]:
                    _shoot_finish(agent, sh, "the target left the view --")
                else:
                    agent._note_failure("shoot_bow")
                    agent.memory.add_note(_no_entity_note(sh, "no target in view"))
                return None
            sh["stage"] = "settle"
            return _sweep_step(sh, mk_act)
        sh["miss"] = 0
        ex, ey = _aim_error(agent, hit)
        # An arrow falls on the way, so the aim point sits ABOVE the blob centre (not a
        # bias on the camera command -- that would only move the loop's equilibrium and
        # the centring test would never pass). The blob's pixel height stands in for
        # distance: a mob 3 blocks off is ~200 px tall and needs no lift, one at 12
        # blocks is ~30 px and needs a few degrees. 0.19 degrees per pixel vertically.
        ey -= max(0.0, min(5.0, 110.0 / max(float(hit[4]), 8.0))) / 0.19
        if abs(ex) > AIM_TOL_X or abs(ey) > AIM_TOL_Y:
            sh["stage"] = "settle"
            return _still(sh, mk_act(camera=_camera_toward(ex, ey)))
        sh["stage"], sh["t"], sh["aimed"] = "draw", 0, 0
        return _still(sh, mk_act())

    if sh["stage"] == "draw":
        sh["t"] += 1
        if sh["t"] <= sh["draw"]:
            return _still(sh, mk_act(use=1))
        sh["stage"], sh["t"] = "release", 0
        return _still(sh, mk_act())          # the release tick fires the arrow

    # release: settle, count the shot, look again for the next one
    sh["t"] += 1
    if sh["t"] < 8:
        return _still(sh, mk_act())
    sh["fired"] += 1
    sh["stage"], sh["t"] = "settle", 0
    return _still(sh, mk_act())


# -- block_with_shield --------------------------------------------------------------

def block_with_shield(cur, info: dict, ticks: int = 60
                      ) -> tuple[list[dict[str, Any]], str]:
    """Raise a shield (hold `use` with it selected) for `ticks`, verified on health."""
    txt = "block_with_shield"
    acts, err = MW._prep_item(cur, info, "shield", txt)
    if err:
        return [], err
    t = max(10, min(200, int(ticks)))
    st = {"ticks": t, "t": 0, "label_txt": txt, "base": None, "still": 0}
    acts.append(macros.marker("_shield", st, t + 10))
    return acts, f"{txt}: shield raised for {t} ticks"


@macros.tick("_shield", shrink="ticks", combat=True)
def _shield_tick(agent, sd: dict[str, Any], mk_act):
    if _gate(agent, sd):
        return None
    if sd["base"] is None:
        sd["base"] = {"hp": _hp(agent), "use": agent.stat_now("use_item", "shield")}
    sd["t"] += 1
    if sd["t"] <= sd["ticks"]:
        return _still(sd, mk_act(use=1))
    if sd["t"] <= sd["ticks"] + 6:
        return _still(sd, mk_act())
    hp, hp0 = _hp(agent), sd["base"]["hp"]
    used = agent.stat_now("use_item", "shield") - sd["base"]["use"]
    lost = (hp0 - hp) if (hp is not None and hp0 is not None) else None
    agent.cursor_stats["shield_blocks"] = agent.cursor_stats.get("shield_blocks", 0) + 1
    agent.memory.add_note(
        f"block_with_shield: shield held up {sd['ticks']} ticks, "
        + (f"health {hp0:.1f} -> {hp:.1f}" if lost is not None else "health unknown")
        + (f" ({lost:.1f} lost while blocking)" if lost else " (no damage taken)")
        + (f", use_item.shield +{used:g}" if used else "")
        + ". A raised shield only covers the direction you FACE: face_entity first, and "
          "you cannot attack while blocking -- alternate block and fight.")
    return None


# -- use_on_entity / boats ------------------------------------------------------------

def use_on_entity(cur, info: dict, item: str | None = None, ticks: int = 60,
                  label: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Face an entity and right-click it with `item`: shear, lead, milk, feed, hook, board."""
    txt = f"use_on_entity({item or 'held'})"
    acts: list[dict[str, Any]] = []
    if item and "boat" in item:
        # A boat is not a mob but it IS an entity you right-click; the colour band that
        # finds one is registered under "boat".
        label = label or "boat"
    if item and "boat" in item and not gui.find_slots(info, item):
        # You place a boat and then no longer carry it; the thing floating there is an
        # ENTITY and you board it with whatever is in your hand. Naming the boat here
        # says what is being clicked, not what must be held.
        item = None
    if item:
        acts, err = MW._prep_item(cur, info, item, txt)
        if err:
            return [], err
    t = max(20, min(200, int(ticks)))
    st = {"budget": t, "used": 0, "still": 0, "miss": 0, "stage": "settle", "t": 0,
          "item": item, "label": (label or None), "label_txt": txt, "tries": 0,
          "base": None}
    acts.append(macros.marker("_useent", st, t))
    return acts, (f"{txt}: facing the target, then right-clicking it"
                  + (f" (looking for a {label})" if label else ""))


def _useent_finish(agent, ue: dict[str, Any], ok: bool) -> None:
    d = _inv_delta(agent, ue["base"]["inv"])
    dtxt = ", ".join(f"{k} {v:+d}" for k, v in sorted(d.items()))
    used = ((agent.stat_now("use_item", ue["item"]) - ue["base"]["use"])
            if ue["item"] else 0.0)
    pos, pos0 = agent._cur_pos, ue["base"]["pos"]
    moved = (_dist(pos, pos0) if (pos and pos0) else 0.0)
    if ok:
        agent.cursor_stats["use_on_entity_ok"] = (
            agent.cursor_stats.get("use_on_entity_ok", 0) + 1)
        agent.memory.add_note(
            f"{ue['label_txt']}: it registered on the {ue['tries']}. try -- "
            + (dtxt or "no inventory change")
            + (f", use_item.{ue['item']} +{used:g}" if used else "")
            + (f", you moved {moved:.2f} blocks (y {pos0['y']:.2f} -> {pos['y']:.2f}) "
               f"-- that is you getting IN: `boat_forward` to drive, `leave_boat` to "
               f"get out" if moved > 0.4 else "")
            + ".")
        return
    agent._note_failure("use_on_entity")
    agent._flush_tail(
        f"{ue['label_txt']}: nothing registered after {ue['tries']} right-click(s) "
        f"(inventory unchanged, use_item unchanged, you did not move). Either the "
        f"crosshair missed the hitbox -- entity reach is 3 blocks and the aim must sit "
        f"on the BODY, so walk 1-2 blocks closer and call face_entity first -- or the "
        f"item does not act on that mob (shears work on a sheep, a bucket on a cow, a "
        f"lead on any animal, food on the animal that eats it). NOTE: shearing puts "
        f"the wool ON THE GROUND, not in your inventory, and nothing here can see a "
        f"dropped item -- if the sheep looks bare in the frame it worked, and "
        f"collect_drops picks the wool up.",
        "useent_failed_flush")


@macros.tick("_useent", shrink="budget", combat=True)
def _useent_tick(agent, ue: dict[str, Any], mk_act):
    ue["used"] = int(ue.get("used", 0)) + 1
    _track(agent, ue)
    return _useent_step(agent, ue, mk_act)


def _useent_step(agent, ue: dict[str, Any], mk_act):
    if _gate(agent, ue):
        return None
    if ue["base"] is None:
        ue["base"] = {"inv": dict(agent._cur_inv), "pos": dict(agent._cur_pos or {}),
                      "use": (agent.stat_now("use_item", ue["item"]) if ue["item"]
                              else 0.0)}
    if ue["used"] > ue["budget"]:
        if ue["tries"]:
            _useent_finish(agent, ue, False)
        else:
            agent._note_failure("use_on_entity")
            agent.memory.add_note(_no_entity_note(ue, "never got a click in"))
        return None

    if ue["stage"] == "settle":
        if int(ue.get("still", 0)) >= STILL_MIN:
            ue["stage"] = "aim"
            return _useent_step(agent, ue, mk_act)
        return _still(ue, mk_act())

    if ue["stage"] == "aim":
        hit = _detect(agent, ue)
        if hit is None:
            ue["miss"] += 1
            if ue["miss"] >= MISS_MAX:
                agent._note_failure("use_on_entity")
                agent.memory.add_note(_no_entity_note(ue, "no entity in view"))
                return None
            ue["stage"] = "settle"
            return _sweep_step(ue, mk_act)
        ue["miss"] = 0
        ex, ey = _aim_error(agent, hit)
        # Retry 2 aims a fifth of the blob lower, retry 3 a fifth higher: the centroid
        # of a silhouette is not always the centre of the hitbox (a sheep's fleece is
        # taller than its body, a boat is wider than it is tall).
        ey += (0.0, 0.20 * hit[4], -0.20 * hit[4])[min(ue["tries"], 2)]
        if abs(ex) > AIM_TOL_X or abs(ey) > AIM_TOL_Y:
            ue["stage"] = "settle"
            return _still(ue, mk_act(camera=_camera_toward(ex, ey)))
        ue["stage"], ue["t"] = "click", 0
        return _useent_step(agent, ue, mk_act)

    if ue["stage"] == "click":
        ue["t"] += 1
        if ue["t"] == 1:
            ue["tries"] += 1
        if ue["t"] <= 2:
            return _still(ue, mk_act(use=1))
        ue["stage"], ue["t"] = "verify", 0
        return _still(ue, mk_act())

    ue["t"] += 1
    pos, pos0 = agent._cur_pos, ue["base"]["pos"]
    ok = (bool(_inv_delta(agent, ue["base"]["inv"]))
          or (ue["item"] and agent.stat_now("use_item", ue["item"]) > ue["base"]["use"])
          or (pos and pos0 and _dist(pos, pos0) > 0.4))
    if ok:
        _useent_finish(agent, ue, True)
        return None
    if ue["t"] < 10:
        return _still(ue, mk_act())
    if ue["tries"] >= 3:
        _useent_finish(agent, ue, False)
        return None
    ue["stage"], ue["t"] = "settle", 0
    return _still(ue, mk_act())


def leave_boat(ticks: int = 12) -> list[dict[str, Any]]:
    """Sneak out of a boat (or off a bed / a horse), verified on the measured y."""
    return [macros.marker("_leaveboat", {"t": 0, "ticks": max(4, min(40, int(ticks))),
                                         "label_txt": "leave_boat", "base": None,
                                         "still": 0}, 24)]


@macros.tick("_leaveboat", moving=True)
def _leaveboat_tick(agent, lb: dict[str, Any], mk_act):
    if lb["base"] is None:
        lb["base"] = dict(agent._cur_pos or {})
    lb["t"] += 1
    if lb["t"] <= lb["ticks"]:
        return mk_act(sneak=1)
    if lb["t"] <= lb["ticks"] + 8:
        return mk_act()
    pos, pos0 = agent._cur_pos, lb["base"]
    dy = (pos["y"] - pos0["y"]) if (pos and pos0) else 0.0
    moved = _dist(pos, pos0) if (pos and pos0) else 0.0
    if dy > 0.2 or moved > 0.4:
        agent.cursor_stats["left_boat"] = agent.cursor_stats.get("left_boat", 0) + 1
        agent.memory.add_note(
            f"leave_boat: out -- y {pos0['y']:.2f} -> {pos['y']:.2f} ({dy:+.2f}), "
            f"moved {moved:.2f} blocks. The boat is still floating where you left it; "
            f"use_on_entity(oak_boat) gets back in, and attacking it breaks it back "
            f"into an item.")
        return None
    agent._note_failure("leave_boat")
    agent.memory.add_note(
        f"leave_boat: y did not change ({pos0.get('y', 0):.2f}) -- you were probably not "
        f"in a boat. Riding shows as y ending in .45 below the water surface.")
    return None


def boat_forward(cur, info: dict, ticks: int = 60, yaw: float | None = None
                 ) -> tuple[list[dict[str, Any]], str]:
    """Drive the boat you are sitting in: hold forward `ticks`, optionally on a heading."""
    t = max(10, min(400, int(ticks)))
    st = {"ticks": t, "t": 0, "yaw": (None if yaw is None else float(yaw)),
          "label_txt": "boat_forward", "base": None, "still": 0, "turn": 0}
    return ([macros.marker("_boatfwd", st, t + 30)],
            f"boat_forward: {t} ticks"
            + (f" on heading yaw {float(yaw):.0f}" if yaw is not None else " ahead"))


@macros.tick("_boatfwd", shrink="ticks", moving=True)
def _boatfwd_tick(agent, bf: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if bf["base"] is None:
        bf["base"] = dict(pos or {})
    if bf["yaw"] is not None and pos and bf["turn"] < 24:
        dy = MW.norm_yaw_delta(bf["yaw"], pos["yaw"])
        if abs(dy) > 4.0:
            bf["turn"] += 1
            return mk_act(camera=[0.0, max(-25.0, min(25.0, dy))])
    bf["t"] += 1
    if bf["t"] <= bf["ticks"]:
        return mk_act(forward=1)
    if bf["t"] <= bf["ticks"] + 6:
        return mk_act()
    pos0 = bf["base"]
    moved = (math.hypot(pos["x"] - pos0["x"], pos["z"] - pos0["z"])
             if (pos and pos0) else 0.0)
    agent.cursor_stats["boat_ticks"] = (
        agent.cursor_stats.get("boat_ticks", 0) + bf["ticks"])
    agent.memory.add_note(
        f"boat_forward: {bf['ticks']} ticks of forward moved you {moved:.1f} blocks to "
        f"({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f}), yaw {pos['yaw']:.0f}."
        + ("" if moved > 1.0 else " That is barely any movement: you are probably NOT "
                                 "in the boat (use_on_entity(oak_boat) to board it) or "
                                 "it is aground -- a boat only moves on water or ice."))
    return None


# -- registration ---------------------------------------------------------------------

def register_all(register, Procedure) -> None:
    register(Procedure(
        "face_entity",
        "Turn the crosshair onto the nearest ENTITY in view and stop when it is "
        "centred: a mob (it is found by the motion it makes against a still world, and "
        "by its colour), a boat, an animal. This is the aim step every other entity "
        "action needs -- there is no entity channel in the observation, so a mob has no "
        "coordinate you can look_at. `label` (zombie, skeleton, spider, creeper, "
        "enderman, pig, cow, sheep, chicken, wolf, witch, blaze, phantom, or boat) narrows the "
        "colour search and makes it much more reliable. Says what it found and where "
        "you now face; says 'nothing in view' when there is nothing, and then you "
        "should scan_around or turn.",
        face_entity, needs_cursor=True, needs_info=True,
        preconditions="No screen open. The entity must be somewhere in the current "
                      "view (roughly +-50 degrees); turn first if it is behind you.",
        params={"ticks": "budget, 10-200 (default 60)",
                "label": "mob name to look for (optional but recommended)"}))
    register(Procedure(
        "fight",
        "Melee an entity to death: selects your best sword (or the weapon you name), "
        "faces the target, walks in when the swings are not landing, and PULSES attack "
        "on the sword cooldown until it dies. Reports swings, hits landed "
        "(use_item.<weapon>), damage dealt, the kill (kill_entity) and the health you "
        "lost. Stops early and says so on: the kill, the target leaving view, or your "
        "health falling to `retreat_hp` (it backs off ~3 blocks first). Against a "
        "SKELETON close the distance fast before you start -- it out-ranges you; "
        "against a creeper hit and step back; a spider is fast and low, aim down.",
        fight, needs_cursor=True, needs_info=True,
        preconditions="No screen open, the mob in front of you (call face_entity first "
                      "if it is not), and a weapon carried (bare hands work but take "
                      "three times as long). Eat first if health is low.",
        params={"ticks": "budget, 40-400 (default 300)",
                "retreat_hp": "back off at this health (default 6)",
                "weapon": "item to fight with (default: your best sword/axe)",
                "label": "mob name to look for (optional)"}))
    register(Procedure(
        "shoot_bow",
        "Shoot arrows at an entity: faces it, holds the draw >= 25 ticks, releases, "
        "re-faces, `shots` times. Verified on use_item.bow and the arrow count; the "
        "note reports the damage dealt and any kill. The right tool for a phantom "
        "overhead, a skeleton across a gap, or softening a mob before melee.",
        shoot_bow, needs_cursor=True, needs_info=True,
        preconditions="A bow AND arrows carried, no screen open, the target in view. "
                      "Arrows drop over distance -- past ~10 blocks aim above it.",
        params={"shots": "arrows to fire, 1-10 (default 3)",
                "draw": "draw ticks, 25-60 (default 25; a full draw is 25)",
                "label": "mob name to look for (optional)"}))
    register(Procedure(
        "block_with_shield",
        "Raise your shield for `ticks` and report the health you lost while it was up. "
        "A raised shield only covers the direction you FACE and you cannot attack while "
        "it is up, so the pattern is: face_entity, block through its swing, then fight.",
        block_with_shield, needs_cursor=True, needs_info=True,
        preconditions="A shield carried (the macro moves it to the hotbar itself), no "
                      "screen open, facing the attacker.",
        params={"ticks": "how long to hold the block, 10-200 (default 60)"}))
    register(Procedure(
        "use_on_entity",
        "Right-click an ENTITY with an item: shears on a sheep (wool), a bucket on a "
        "cow (milk), a lead on any animal, food to feed/breed it, a fishing rod cast at "
        "it, or `oak_boat` on a boat floating in front of you to GET IN. Faces it "
        "first, clicks, and retries with a slightly different aim up to three times; "
        "verified on the inventory, use_item, or your position jumping (that is you "
        "boarding). Says which of those moved.",
        use_on_entity, needs_cursor=True, needs_info=True,
        preconditions="Within 3 blocks of the entity (entity reach is shorter than "
                      "block reach), no screen open, the item carried.",
        params={"item": "item to use (shears, bucket, lead, wheat, fishing_rod, "
                        "oak_boat...; omit to use what you hold)",
                "ticks": "budget, 20-200 (default 60)",
                "label": "mob name to look for (optional)"}))
    register(Procedure(
        "boat_forward",
        "Drive the boat you are sitting in: hold forward for `ticks`, optionally after "
        "turning to an absolute heading. Reports how far you actually moved -- if that "
        "is under a block you are not in the boat, or it is aground (a boat only moves "
        "on water or ice).",
        boat_forward, needs_cursor=True, needs_info=True,
        preconditions="You are IN the boat (use_on_entity(item='oak_boat') first) and "
                      "there is open water ahead.",
        params={"ticks": "10-400 (default 60)",
                "yaw": "absolute heading to steer onto first (optional; 0 = +z, "
                       "90 = -x, -90 = +x)"}))
    register(Procedure(
        "leave_boat",
        "Get out of the boat (sneak), verified on your y rising back out of the hull.",
        lambda ticks=12: leave_boat(ticks),
        params={"ticks": "sneak ticks (default 12)"}))
