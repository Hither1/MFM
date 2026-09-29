"""`harvest_tree`: the wood phase as one closed loop instead of a model-turn loop.

Why. Across the 20 from-scratch arms archived so far, 2,232 `chop_tree` calls broke a
log 473 times (21%); 1,110 ran their 75 ticks with nothing breaking (out of reach)
and 477 broke leaves or dirt. Each miss cost a model turn to notice and another to
"walk 2-3 blocks forward and chop again" -- 2,000-8,000 ticks per run in wood
macros, the first ~3,000 steps of every run, and a second helping when the torch
rule sends the run back for charcoal logs (one run: 3,456 macro ticks for 5 logs
between its stone pickaxe and its furnace). A calibration episode showed that the
trunk's apparent size is no reach test
(dark spruce bark passes the colour mask in a 16-26 px strip even when adjacent),
but that walking at the centred trunk until it physically blocks the avatar puts
the crosshair within reach every time: the chop from there broke the log in 64
ticks. The first live smoke then showed the second failure: after the eye-level
log is gone the view looks THROUGH the gap, and a detector-guided re-aim centres on
a distant trunk seen through the hole (75 empty ticks, then "no trunk").

So the loop is: centre the trunk (the aim_at_tree servo), walk at it with yaw
corrections riding on the walk until the avatar stops moving, find out WHAT stopped
it, hold attack until the stat stream says a log broke -- and from then on the
geometry is known, so no more detector and NO MOVEMENT until the trunk is used up:
from the spot where the trunk stopped the avatar (0.3 from the face) the foot block
is 54 degrees down and the blocks above the eye-level gap are 48, 67 and 74 degrees
up, all within reach -- five logs without taking a step. Every version that moved
between chops paid for it: a sweep walked the avatar off its angles (one run), a
fixed forward+jump walk-in flew through the gap on jump momentum (one run), and a
position servo still overshot the column by a block when the first ticks read
"stuck" and jumped (one run).

v5: "the avatar stopped" is not "the trunk stopped it". v4 read five
static ticks as arrival and, at every tree that was not on flat ground, chopped from
2-4 blocks away: the counter fired while the avatar climbed a one-block ledge or
pressed against a terrace (one run calls at steps 293/604/1080 -- 0 logs, 1 broken
far away, ~270 ticks each; replayed from their live poses in the sim). No frame
statistic separates bark in the face from a dirt step (the bark mask fires on earth
too, and its recall on real bark is ~0.55), so the loop PROBES: a jump-and-walk
(a one-block step is climbed and the walk goes on), then the foot swing at 54
degrees for 22 ticks -- earth or grass there breaks in 15-18 ticks by hand and says
"ground ahead, not the trunk" (walk on; the third such probe gives up and chops from
here with an honest note), while a log absorbs the swing and the chop simply carries
on at the foot. Near the trunk the detector loses it (a trunk within ~2.5 blocks is
wider than its run limit, and raising that limit reads every dirt face as bark), so
once a centred run has been seen close the walk holds its heading and ignores
neighbouring trunks instead of steering off to them (the drive-by of one run's second
call). Bark near the centre re-centres the yaw before each upper chop. Leaves in the
way of the eye chop are simply broken (two non-wood breaks -> re-aim); an eye chop
that breaks nothing in 75 ticks means the block that stopped us was not the trunk,
so the loop walks again and gives up after the second such probe. One sweep at the
end, starting with a hop toward the column's foot where the drops collect.

Pure functions over a JSON-able state dict, so the agent's queue stays serialisable
and the loop can be driven against a real sim from a script.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from mcu_worldmodel import vision

#: Walking budget per approach; sprinting covers ~0.28 blocks a tick, so this is
#: 40+ blocks -- a trunk further than that was never "in view" in a useful sense.
APPROACH_TICKS = 160
#: Attack ticks with no break before a chop is declared empty. A log by hand is
#: 60 ticks; leaves ~6; dirt/grass 15-18.
CHOP_EMPTY_TICKS = 75
#: Horizontal movement per tick below which the avatar counts as static, and the
#: static ticks that start the arrival probes.
STUCK_EPS = 0.02
STATIC_TICKS = 3
#: The jump probe: two ticks of jump, then walk while airborne, then read the
#: landing -- a one-block step leaves the avatar a block higher (or further on),
#: a trunk or wall leaves it where it was.
JUMP_PROBE_TICKS = 14
#: Attack ticks of the foot probe at FOOT_PITCH: earth/grass ahead breaks well
#: inside this (15-18 by hand); a log does not (60). After ground broke there, the
#: eye probe swings at eye level for as long: the upper block of a two-high step
#: or a fence of leaves goes the same way, and the walk continues through the gap.
FOOT_PROBE_TICKS = 22
EYE_PROBE_TICKS = 22
#: Ground probes (each says "not the trunk yet") before the walk gives up and
#: chops from where it stands.
FOOT_PROBES_MAX = 3
#: A detection this wide (px) marks the trunk as NEAR (within ~6 blocks); from then
#: on a re-aim may accept a run wider than the stock limit, but only within
#: COMMIT_JUMP_PX of where the trunk was (a dirt face elsewhere passes the same
#: mask). Tried and dropped (sims): holding the tracked x during the
#: walk-in, or steering by the wide run -- both lost the spawn trunk that the
#: plain servo reaches.
NEAR_DET_W = 50
COMMIT_JUMP_PX = 100
#: Ticks without any detection before the walk re-aims.
NODET_TICKS = 8
#: Before each chop, bark this far (px) off the centre re-centres the yaw. The
#: walk-in stops with the trunk up to ~20 degrees off-axis (the spawn spruce:
#: 0.3 blocks ahead, 0.3 to the side), which is ~140 px -- outside v4's 120-px
#: window, so its upper chops were aimed at the sky beside the trunk.
RECENTER_PX = 220
RECENTER_TICKS = 12
#: Ticks of the end sweep and its movement pattern; the sweep also ends after
#: SWEEP_IDLE_TICKS without a log arriving (drops that are coming arrive early).
SWEEP_TICKS = 48
SWEEP_IDLE_TICKS = 24
SWEEP_CYCLE = (("forward", 8), ("back", 16), ("forward", 8), ("left", 8), ("right", 16),
               ("left", 8))
#: A far chop's drops lie blocks ahead, so the end sweep IS the collection: ticks kept
#: back for it (the pitch step and the swing of one more chop, then the hop and the
#: lap). With less than this left, the ladder ends and the sweep starts instead of
#: another chop. One run stopped on the ledge 3 blocks short of the spawn
#: spruce, broke 3 logs from there and spent the whole 400-tick budget on the chops:
#: the sweep never ran, 0 collected, and every later call saw dirt ("no trunk").
SWEEP_RESERVE = 12 + CHOP_EMPTY_TICKS + 14 + SWEEP_TICKS
#: Pitch (degrees, + is down) of the trunk's foot block from an avatar the trunk
#: blocks: the ray must pass the face (0.3-0.7 ahead) BELOW 1.0, i.e. steeper than
#: atan(0.62/0.3) = 64 degrees. v4's 54 reached the foot only because its eye chop
#: had already emptied the block above; probing foot-first, 54 hits that block.
FOOT_PITCH = 66.0
#: The eye-level block, and the blocks above it from the same spot (eye 1.62 up,
#: column centre ~0.8 ahead): 2.5 / 3.5 / 4.5 blocks up.
EYE_PITCH = 0.0
OUTSIDE_LADDER = (-48.0, -67.0, -74.0)
#: A bark run narrower than this (px) when the chop starts means the trunk is NOT
#: in the face: the walk was stopped short (the spawn spruce: a one-block step with
#: leaves over it, the trunk 3+ blocks on). The eye ray still reaches its log, and
#: the blocks above are at the angles for THAT distance (from the run width: a
#: one-block trunk spans 2*atan(0.5/d) of a ~102-degree, 640-px view) -- not the
#: touching angles, which from 3 blocks point at the sky. The foot is skipped:
#: from there the terrace is in the way.
FAR_RUN_W = 200
FAR_D_MIN, FAR_D_MAX = 1.2, 4.0
EYE_HEIGHT = 1.62
HFOV_DEG = 102.0


def new_state(logs: int = 3, budget: int = 500) -> dict[str, Any]:
    return {"target": max(1, int(logs)), "budget": max(60, min(1500, int(budget))),
            "used": 0, "state": "aim", "after_aim": "approach", "aim_t": 0, "miss": 0,
            "app_t": 0, "nodet": 0, "stuck": 0, "last": None, "near_t": -1000,
            "probe_t": 0, "probe_y0": None, "probe_xz0": None, "probes": 0,
            "probe_pos": None, "blocked": False, "last_w": None, "far": False,
            "chop_t": 0,
            "chop_logs": None, "chop_other": None, "chop_kind": "eye",
            "pitch_target": None, "pitch_t": 0, "recenter_t": 0, "ladder": [],
            "sweep_t": 0, "sweep_inv": None,
            "base_logs": None, "base_other": None, "base_inv": None, "prefer_x": None,
            "approaches": 0, "chops": 0, "empties": 0, "clears": 0,
            "note": None}


def _summary(hv: dict[str, Any], gained: int, broken: int, why: str) -> str:
    tail = (" The walk-in was stopped short of the trunk by terrain (ground broke under "
            "three foot probes), so the chops were made from a distance -- reach the "
            "trunk's foot from another side and harvest again."
            if hv.get("blocked") else "")
    return (f"harvest_tree: {gained} log(s) collected ({broken} broken) in {hv['used']} "
            f"ticks -- {hv['approaches']} approach(es), {hv['chops']} chop(s), "
            f"{hv['empties']} empty, {hv['clears']} leaf-clear(s). {why}{tail}")


def tick(hv: dict[str, Any], frame, pos: dict[str, float] | None, log_breaks: float,
         other_breaks: float, inv_logs: int, gui_open: bool = False
         ) -> tuple[dict[str, Any] | None, str | None]:
    """One tick. Returns (action kwargs, note); action None means the macro is done."""
    if hv["base_inv"] is None:
        hv["base_logs"], hv["base_other"], hv["base_inv"] = log_breaks, other_breaks, inv_logs
    gained = int(inv_logs - hv["base_inv"])
    broken = int(log_breaks - hv["base_logs"])
    if gui_open:
        return None, ("harvest_tree stopped at once: a SCREEN is open, and movement "
                      "does nothing in the world while it is. Close it, then harvest.")
    if gained >= hv["target"]:
        return None, _summary(hv, gained, broken, "Target reached.")
    if hv["used"] >= hv["budget"]:
        if broken > gained:
            why = (f"the {broken - gained} log(s) that broke lie at the trunk's foot "
                   f"-- walk there (collect_drops) before anything else, then "
                   f"harvest_tree again for the rest.")
        elif hv["approaches"]:
            why = ("Bark was in view; the trunk may stand across a drop or behind "
                   "leaves -- walk around and harvest again.")
        else:
            why = "No trunk was ever centred: walk toward visible LEAVES first."
        return None, _summary(hv, gained, broken,
                              f"Budget of {hv['budget']} ticks spent; {why}")
    hv["used"] += 1
    state = hv["state"]
    det = None
    if state in ("aim", "approach", "pitch") and frame is not None:
        fr = np.asarray(frame)
        det = vision.find_tree_trunk(fr, prefer_x=hv.get("prefer_x"))
        if (det is None and state == "aim" and hv["near_t"] > 0
                and hv.get("prefer_x") is not None):
            # The tracked trunk has grown past the stock run limit (within ~2.5
            # blocks): a re-aim accepts a wide run, but only where the trunk was --
            # a dirt face elsewhere passes the same mask and is not it.
            wide = vision.find_tree_trunk(fr, prefer_x=hv["prefer_x"],
                                          max_w=vision.TRUNK_NEAR_MAX_W)
            if wide is not None and abs(wide[0] - hv["prefer_x"]) <= COMMIT_JUMP_PX:
                det = wide
        if det is None and state == "pitch":
            # Between chops the avatar touches the trunk: any wide bark column near
            # the centre is it (looking up, the column above the gap is what shows).
            wide = vision.find_tree_trunk(fr, prefer_x=320.0,
                                          max_w=vision.TRUNK_NEAR_MAX_W)
            if wide is not None and abs(wide[0] - 320.0) <= RECENTER_PX:
                det = wide
        if det is not None:
            hv["prefer_x"] = int(det[0])
            if len(det) > 3:
                hv["last_w"] = int(det[3])
        elif state == "approach" and hv["near_t"] > 0 and hv.get("prefer_x") is not None:
            # Book-keeping only (no steering): the width of the trunk in the face,
            # which the stock limit hides, decides between the touching ladder and
            # the far one when a chop starts from this spot.
            wide = vision.find_tree_trunk(fr, prefer_x=hv["prefer_x"],
                                          max_w=vision.TRUNK_NEAR_MAX_W)
            if wide is not None and abs(wide[0] - hv["prefer_x"]) <= COMMIT_JUMP_PX:
                hv["last_w"] = int(wide[3])

    if state == "aim":
        if det is None:
            hv["miss"] += 1
            if hv["miss"] >= 6:
                if hv["after_aim"] == "chop":
                    # Blocked with nothing detected: a wide, close trunk can defeat
                    # the column detector. Chop what the crosshair is on anyway.
                    _start_chop(hv, inv_logs)
                    return {}, None
                if broken or gained:
                    return None, _summary(hv, gained, broken,
                                          "The trunk left the view; re-run harvest_tree "
                                          "facing bark to continue.")
                return None, ("harvest_tree: no trunk detected (6 frames). Turn toward "
                              "visible LEAVES and retry -- a tree's leaves mark where "
                              "its trunk stands; in a treeless view, travel toward the "
                              "nearest leaf mass first.")
            return {}, None
        hv["miss"] = 0
        ex, ey = det[0] - 320.0, det[1] - 180.0
        hv["aim_t"] += 1
        if (abs(ex) <= 10.0 and abs(ey) <= 10.0) or hv["aim_t"] > 40:
            if hv["after_aim"] == "chop":
                _start_chop(hv, inv_logs)
            else:
                _enter(hv, "approach")
            return {}, None
        dp = max(-20.0, min(20.0, ey * 0.19 * 0.8))
        dy = max(-20.0, min(20.0, ex * 0.14 * 0.8))
        return {"camera": (dp, dy)}, None

    if state == "approach":
        hv["app_t"] += 1
        if pos is not None:
            last = hv.get("last")
            if last is not None:
                moved = math.hypot(pos["x"] - last[0], pos["z"] - last[1])
                hv["stuck"] = hv["stuck"] + 1 if moved < STUCK_EPS else 0
            hv["last"] = (pos["x"], pos["z"])
            if hv["stuck"] >= STATIC_TICKS:
                # Something stops the walk. Find out what before swinging at it --
                # and before any re-aim: the trunk vanishes from the detector
                # exactly when it is in the face.
                pp = hv.get("probe_pos")
                if (pp is not None and hv["stuck"] >= STATIC_TICKS
                        and math.hypot(pos["x"] - pp[0], pos["z"] - pp[1]) < 0.3):
                    # Still on the spot where ground broke under the last probe:
                    # what holds us is not that ground. Chop from here, eye first.
                    _start_chop(hv, inv_logs)
                    return {}, None
                _enter(hv, "probe_jump")
                hv["probe_y0"] = float(pos.get("y", 0.0))
                hv["probe_xz0"] = (pos["x"], pos["z"])
                return {}, None
        if det is None:
            hv["nodet"] += 1
            if hv["nodet"] >= NODET_TICKS:
                _enter(hv, "aim", after="approach")
                return {}, None
            dy = 0.0
        else:
            hv["nodet"] = 0
            if len(det) > 3 and det[3] >= NEAR_DET_W:
                hv["near_t"] = hv["used"]
            dy = max(-8.0, min(8.0, (det[0] - 320.0) * 0.14 * 0.8))
        if hv["app_t"] >= APPROACH_TICKS:
            _enter(hv, "aim", after="chop")
            return {}, None
        return {"forward": 1, "sprint": 1, "camera": (0.0, dy)}, None

    if state == "probe_jump":
        t = hv["probe_t"]
        hv["probe_t"] += 1
        if t < JUMP_PROBE_TICKS:
            return {"forward": 1, "jump": 1 if t < 2 else 0}, None
        y0, xz0 = hv["probe_y0"], hv["probe_xz0"]
        climbed = (pos is not None and y0 is not None
                   and float(pos.get("y", 0.0)) - y0 >= 0.9)
        moved = (pos is not None and xz0 is not None
                 and math.hypot(pos["x"] - xz0[0], pos["z"] - xz0[1]) >= 0.3)
        if climbed or moved:
            _resume_approach(hv)            # a step, not the trunk: walk on
            return {}, None
        _enter(hv, "probe_foot")
        return {}, None

    if state == "probe_foot":
        cur = float(pos["pitch"]) if pos and pos.get("pitch") is not None else None
        hv["pitch_t"] += 1
        if cur is not None and abs(FOOT_PITCH - cur) > 2.0 and hv["pitch_t"] <= 12:
            return {"camera": (max(-20.0, min(20.0, FOOT_PITCH - cur)), 0.0)}, None
        if hv["chop_logs"] is None:
            hv["chop_logs"], hv["chop_other"] = log_breaks, other_breaks
        if log_breaks - hv["chop_logs"] >= 1:
            # The foot log went already (an axe, or a leftover swing): at the trunk.
            hv["chops"] += 1
            hv["ladder"] = [("pitch", EYE_PITCH, "eye")] + [
                ("pitch", p, "up") for p in OUTSIDE_LADDER]
            _next(hv, inv_logs)
            return {}, None
        if other_breaks - hv["chop_other"] >= 1:
            # Earth or grass at the foot angle: ground ahead, not the trunk.
            hv["probes"] += 1
            hv["probe_pos"] = (pos["x"], pos["z"]) if pos is not None else None
            if hv["probes"] >= FOOT_PROBES_MAX:
                hv["blocked"] = True
                _enter(hv, "aim", after="chop")
                return {}, None
            _enter(hv, "probe_eye")         # open the block above it as well
            return {}, None
        if hv["chop_t"] >= FOOT_PROBE_TICKS:
            # Nothing that breaks fast by hand at the foot: the trunk. Keep swinging
            # at the same block -- the progress so far counts.
            hv["state"], hv["chop_kind"] = "chop", "foot"
            hv["ladder"] = [("pitch", EYE_PITCH, "eye")] + [
                ("pitch", p, "up") for p in OUTSIDE_LADDER]
        hv["chop_t"] += 1
        return {"attack": 1}, None

    if state == "probe_eye":
        cur = float(pos["pitch"]) if pos and pos.get("pitch") is not None else None
        hv["pitch_t"] += 1
        if cur is not None and abs(EYE_PITCH - cur) > 2.0 and hv["pitch_t"] <= 12:
            return {"camera": (max(-20.0, min(20.0, EYE_PITCH - cur)), 0.0)}, None
        if hv["chop_logs"] is None:
            hv["chop_logs"], hv["chop_other"] = log_breaks, other_breaks
        if log_breaks - hv["chop_logs"] >= 1:
            # A log at eye level after all: the trunk stands right behind the
            # step. Carry on as if the eye chop had just landed.
            hv["chops"] += 1
            hv["ladder"] = [("pitch", FOOT_PITCH, "foot")] + [
                ("pitch", p, "up") for p in OUTSIDE_LADDER]
            _next(hv, inv_logs)
            return {}, None
        if other_breaks - hv["chop_other"] >= 1 or hv["chop_t"] >= EYE_PROBE_TICKS:
            _resume_approach(hv)            # the gap is open (or was never shut)
            return {}, None
        hv["chop_t"] += 1
        return {"attack": 1}, None

    if state == "chop":
        if hv["chop_logs"] is None:
            hv["chop_logs"], hv["chop_other"] = log_breaks, other_breaks
        kind = hv["chop_kind"]
        if log_breaks - hv["chop_logs"] >= 1:
            hv["chops"] += 1
            _next(hv, inv_logs)                 # the ladder was set when the chop began
            return {}, None
        wrong = other_breaks - hv["chop_other"]
        if wrong >= 2 or (kind != "eye" and wrong >= 1):
            hv["chops"] += 1
            if kind == "eye":
                hv["clears"] += 1
                # Leaves (or dirt) in front of the bark are gone; re-centre and go on.
                _enter(hv, "aim", after="chop" if hv["clears"] < 4 else "approach")
            elif kind == "foot":
                # Earth under the trunk (a mound or a terrace): the blocks above
                # the gap are still in reach from here.
                _next(hv, inv_logs)
            else:
                # Leaves above the trunk: this tree is done.
                _sweep(hv, inv_logs)
            return {}, None
        if hv["chop_t"] >= CHOP_EMPTY_TICKS:
            hv["chops"] += 1
            if kind == "eye":
                hv["empties"] += 1
                if hv["empties"] >= 2:
                    return None, _summary(
                        hv, gained, broken,
                        "Two chops of 75 ticks broke nothing: what stopped the walk was "
                        "not the trunk (a ledge, a fence of leaves, water). Walk around "
                        "to the trunk's other side or approach a different tree, then "
                        "harvest_tree again.")
                _enter(hv, "aim", after="approach")
            elif kind == "foot":
                _next(hv, inv_logs)
            else:
                # Nothing overhead within reach: this tree is done.
                _sweep(hv, inv_logs)
            return {}, None
        hv["chop_t"] += 1
        return {"attack": 1}, None

    if state == "pitch":
        tgt = hv["pitch_target"]
        cur = float(pos["pitch"]) if pos and pos.get("pitch") is not None else None
        hv["pitch_t"] += 1
        if cur is not None and abs(tgt - cur) > 2.0 and hv["pitch_t"] <= 12:
            return {"camera": (max(-20.0, min(20.0, tgt - cur)), 0.0)}, None
        # At the angle: bark near the centre re-centres the yaw (a walk against a
        # terrace slides the avatar sideways; one run's -48 chop hit sky beside the
        # trunk). Straight up the detector sees log ends, not bark, and is skipped.
        hv["recenter_t"] += 1
        if det is not None and hv["recenter_t"] <= RECENTER_TICKS:
            ex = det[0] - 320.0
            if 10.0 < abs(ex) <= RECENTER_PX:
                return {"camera": (0.0, max(-12.0, min(12.0, ex * 0.14 * 0.8)))}, None
        hv["state"], hv["chop_t"] = "chop", 0
        hv["chop_logs"], hv["chop_other"] = None, None
        return {}, None

    if state == "sweep":
        if hv["sweep_inv"] is not None and inv_logs > hv["sweep_inv"]:
            hv["sweep_inv"], hv["sweep_gain_t"] = inv_logs, hv["sweep_t"]
        idle = hv["sweep_t"] - hv.get("sweep_gain_t", 0)
        if hv["sweep_t"] >= SWEEP_TICKS or idle >= SWEEP_IDLE_TICKS:
            return None, _summary(
                hv, gained, broken,
                "This trunk is used up (or its top is out of reach)"
                + ("; some drops were not walked over -- stand ON the trunk's "
                   "foot with collect_drops before leaving" if broken > gained
                   else "")
                + ". Face another trunk and harvest_tree again for more.")
        t = hv["sweep_t"]
        hv["sweep_t"] += 1
        if t < (14 if hv.get("far") else 4):
            # Up against / onto the foot first -- a few blocks of it after far chops.
            return {"forward": 1, "jump": 1}, None
        p, key = (t - 4) % 64, "forward"
        for k, n in SWEEP_CYCLE:
            if p < n:
                key = k
                break
            p -= n
        return {key: 1}, None

    return None, _summary(hv, gained, broken, f"unknown state {state!r}")


def _sweep(hv: dict[str, Any], inv_logs: int) -> None:
    hv["state"], hv["sweep_t"], hv["sweep_inv"] = "sweep", 0, inv_logs
    hv["sweep_gain_t"] = 0


def _next(hv: dict[str, Any], inv_logs: int) -> None:
    """Advance the fixed ladder after a break; a used-up ladder sweeps and ends, and
    so does a far ladder whose remaining budget would not fit a chop AND the sweep."""
    if not hv["ladder"] or (hv.get("far") and hv["budget"] - hv["used"] < SWEEP_RESERVE):
        _sweep(hv, inv_logs)
        return
    stepdef = hv["ladder"].pop(0)
    hv["state"], hv["pitch_target"], hv["pitch_t"] = "pitch", float(stepdef[1]), 0
    hv["recenter_t"] = 0
    hv["chop_kind"] = stepdef[2]


def far_ladder(width: int | None) -> list[tuple[str, float, str]]:
    """Chop angles for a trunk `width` px wide in view: the touching ladder when it
    fills the face, else the eye block then the 2nd-4th blocks above the feet at
    the pitches for the distance the width implies (all inside the 4.5 reach at
    the far end: 4.0 across, 2.9 up)."""
    if width is None or width >= FAR_RUN_W:
        return [("pitch", EYE_PITCH, "eye"), ("pitch", FOOT_PITCH, "foot")] + [
            ("pitch", p, "up") for p in OUTSIDE_LADDER]
    half = math.radians(max(1.0, float(width)) / 640.0 * HFOV_DEG / 2.0)
    d = max(FAR_D_MIN, min(FAR_D_MAX, 0.5 / math.tan(half)))
    ups = [("pitch", -math.degrees(math.atan((k + 0.5 - EYE_HEIGHT) / d)), "up")
           for k in (2, 3, 4)]
    return [("pitch", EYE_PITCH, "eye")] + ups


def _start_chop(hv: dict[str, Any], inv_logs: int) -> None:
    """Begin the chop sequence from where the avatar stands, eye level first: the
    path taken when the loop could not verify the trunk with a probe -- the eye ray
    is the one that reaches a log from a distance. The rest of the ladder follows
    the trunk's last seen width (far_ladder). Every chop goes through its pitch
    step: the camera may still be at the foot probe's angle, and an "eye" chop made
    there hits the ground."""
    hv["ladder"] = far_ladder(hv.get("last_w"))
    hv["far"] = hv["ladder"][1][2] != "foot"      # the drops will lie blocks ahead
    _next(hv, inv_logs)


def _resume_approach(hv: dict[str, Any]) -> None:
    """Back to walking after a probe, without counting a new approach."""
    hv["state"], hv["nodet"], hv["last"], hv["stuck"] = "approach", 0, None, 0


def _enter(hv: dict[str, Any], state: str, after: str | None = None) -> None:
    hv["state"] = state
    if state == "aim":
        hv["aim_t"], hv["miss"] = 0, 0
        hv["after_aim"] = after or "approach"
    elif state == "approach":
        hv["app_t"], hv["nodet"], hv["last"], hv["stuck"] = 0, 0, None, 0
        hv["approaches"] += 1
    elif state == "probe_jump":
        hv["probe_t"] = 0
    elif state in ("probe_foot", "probe_eye"):
        hv["pitch_t"], hv["chop_t"] = 0, 0
        hv["chop_logs"], hv["chop_other"] = None, None
    elif state == "chop":
        hv["chop_t"], hv["chop_logs"], hv["chop_other"] = 0, None, None
