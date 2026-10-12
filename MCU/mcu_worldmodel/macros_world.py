"""World interaction by coordinate: place, use, hold, throw, pillar, build, bridge, scan.

Why. Every building task in the suite ("build a wall / pillar / tower / house / garden /
maze", "lay a carpet", "place an item frame", "decorate the ground", "light up the
surroundings", a nether portal, a snow golem) and every tool task ("use flint and steel",
"pour a water bucket", "till soil and plant seeds", "carve a pumpkin with shears") is the same
motor act for a human: look at a block face, right-click. For the model it was a guess: a
probe placed nothing when the avatar stood off a block's centre and aimed 55
degrees down (the ray landed on the block its own hitbox overlaps, so the game refused),
and every torch/frame/hoe/seed use aimed by eye missed. `[STATE]` is exact, so the aim at a
WORLD BLOCK FACE is trigonometry, done every tick from the live position, and the click is
verified on the `use_item` statistic (a placed block is a `use_item` of it) and the
inventory -- never on the frame.

The pieces:
- `use_at(x, y, z, item, face, hold)`: aim at a face of a block and right-click with an
  item selected; `place_at` is the same with a placement verdict. One closed-loop marker
  (`_useat`): aim (<= 14 ticks), click, verify (<= 6 ticks), try the next candidate face,
  then say what happened.
- `build_wall`, `build_row`, `build_column`, `bridge_forward`: lists of targets compiled
  from the avatar's block and facing (snapped to an axis), executed by ONE marker
  (`_build`) that runs the same place machine target by target, walks to a standing spot
  when the next target is out of reach, tolerates a block that is already there, and
  reports "placed N of M" when its budget ends so the model can resume.
- `pillar_up(n)`: jump-and-place under the feet, each block verified on the measured y.
- `use_held(item, hold)` / `throw(item)` / `eat()`: hold or tap `use` with an item
  selected, verified on the inventory and `use_item`.
- `scan_around(steps)`: turn a full circle, save a frame per heading, tile them into one
  contact sheet attached to the next turn -- the look-around every "find X" task starts with.
- `sleep_in_bed(x, y, z)`: use the bed, wait the night out (isGuiOpen is the bed screen).

Every action goes through `sim.step`; nothing here reads a scoring rule. Parameters are the
model's: which block, where, how many, how high.
"""
from __future__ import annotations

import io
import math
from typing import Any

import numpy as np

from mcu_worldmodel import gui, macros, vision
from mcu_worldmodel.milestones import slot_is_empty

EYE = 1.62
#: Survival block reach, from the eye. 4.5 in vanilla; 4.4 leaves margin for the aim
#: point sitting 0.02 inside the support block.
REACH = 4.4
#: Player hitbox half-width and height: a block that intersects it cannot be placed.
HALF_W, HEIGHT = 0.3, 1.8
#: Aim tolerance (degrees) before the click.
AIM_TOL = 1.5
AIM_TICKS = 14
#: The use_item statistic lags the inventory by several ticks (a staged scene).
VERIFY_TICKS = 10
#: Charged per placement inside `_build`; a real one costs ~10-20.
PLACE_COST = 24
#: bridge_forward: where to stand relative to a block's centre (0.5 is the edge; the
#: hitbox keeps the avatar up to ~0.25 past it), the aim tolerance from there, and how
#: close the walk must get before it stops (it then never passes 0.75).
BRIDGE_OVERHANG = 0.70
BRIDGE_AIM_TOL = 0.7
BRIDGE_WALK_TOL = 0.06
#: Face names and the unit offset from the TARGET to its SUPPORT block.
FACE_OFFSET = {"below": (0, -1, 0), "above": (0, 1, 0), "north": (0, 0, -1),
               "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0)}
#: Foods the `eat` macro picks from the hotbar, best first.
FOODS = ("cooked_beef", "cooked_porkchop", "cooked_mutton", "cooked_chicken", "steak",
         "golden_apple", "bread", "cooked_cod", "cooked_salmon", "baked_potato", "apple",
         "carrot", "melon_slice", "cookie", "beef", "porkchop", "mutton", "chicken",
         "potato", "beetroot", "sweet_berries")


# -- geometry ---------------------------------------------------------------

def facing(yaw: float) -> tuple[float, float]:
    """Horizontal unit vector the avatar faces: yaw 0 -> +z, yaw 90 -> -x."""
    r = math.radians(yaw)
    return (-math.sin(r), math.cos(r))


def axis_facing(yaw: float) -> tuple[int, int]:
    """`facing` snapped to the nearest axis: buildings are axis-aligned."""
    dx, dz = facing(yaw)
    if abs(dx) >= abs(dz):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dz > 0 else -1)


def block_of(pos: dict[str, float]) -> tuple[int, int, int]:
    return (math.floor(pos["x"]), math.floor(pos["y"]), math.floor(pos["z"]))


def aim_point(target: tuple[int, int, int], face: str, inset: float = 0.45
              ) -> tuple[float, float, float]:
    """The point to look at: the centre of the TARGET cell moved `inset` toward the
    face it shares with the support (0.5 = exactly on the shared plane).

    Placing uses 0.5: the ray must meet the support's face ON the plane, because
    from a steep angle a point short of the plane makes the ray cross it lower --
    below the face's bottom edge when bridging from an overhang (a probe:
    the block went one level down every time). Using a block (a bed, a
    grass block, a chest) uses 0.45, inside the target: a low block like a bed (0.56
    high) is still hit, where a point on its top plane would fly over it."""
    ox, oy, oz = FACE_OFFSET[face]
    x, y, z = target
    return (x + 0.5 + ox * inset, y + 0.5 + oy * inset, z + 0.5 + oz * inset)


def angles_to(pos: dict[str, float], point: tuple[float, float, float]
              ) -> tuple[float, float, float]:
    """(pitch, yaw, distance) from the eye at `pos` to `point`; the same convention
    procedures.look_at uses (checked against live headings)."""
    dx = point[0] - pos["x"]
    dy = point[1] - (pos["y"] + EYE)
    dz = point[2] - pos["z"]
    horiz = math.hypot(dx, dz)
    yaw = math.degrees(math.atan2(-dx, dz))
    pitch = (math.degrees(-math.atan2(dy, horiz)) if horiz > 1e-6
             else (90.0 if dy < 0 else -90.0))
    return (max(-90.0, min(90.0, pitch)), yaw, math.sqrt(dx * dx + dy * dy + dz * dz))


def overlaps_player(target: tuple[int, int, int], pos: dict[str, float]) -> bool:
    x, y, z = target
    return (x < pos["x"] + HALF_W and x + 1 > pos["x"] - HALF_W
            and z < pos["z"] + HALF_W and z + 1 > pos["z"] - HALF_W
            and y < pos["y"] + HEIGHT and y + 1 > pos["y"])


def norm_yaw(yaw: float) -> float:
    """A yaw folded into [-180, 180) (the engine's own accumulates past 360)."""
    return (float(yaw) + 180.0) % 360.0 - 180.0


def norm_yaw_delta(target: float, cur: float) -> float:
    return (target - cur + 180.0) % 360.0 - 180.0


def face_visible(pos: dict[str, float], target: tuple[int, int, int], face: str,
                 solid: set, floor_y: float | None) -> bool:
    """Can the eye at `pos` see the SUPPORT's face shared with `target`?

    Two conditions the engine enforces and a build must respect (a staged scene,
    from the ground the third block of a column landed in FRONT of the
    column, because the ray met the support's front face before its hidden top):
    the eye must be on the target's side of the shared plane, and no known solid
    cell (`solid`, plus everything at or below `floor_y`) may sit on the ray between
    the eye and the plane."""
    ox, oy, oz = FACE_OFFSET[face]
    tx, ty, tz = target
    ex, ey, ez = pos["x"], pos["y"] + EYE, pos["z"]
    # the plane coordinate along the face's axis, and which side the eye must be on
    if oy:
        plane, e = (ty if oy < 0 else ty + 1), ey
        if (oy < 0 and e <= plane) or (oy > 0 and e >= plane):
            return False
    elif ox:
        plane, e = (tx if ox < 0 else tx + 1), ex
        if (ox < 0 and e <= plane) or (ox > 0 and e >= plane):
            return False
    else:
        plane, e = (tz if oz < 0 else tz + 1), ez
        if (oz < 0 and e <= plane) or (oz > 0 and e >= plane):
            return False
    # march the ray in small steps up to the plane; any solid cell on the way blocks
    px, py, pz = aim_point(target, face, 0.5)
    dx, dy, dz = px - ex, py - ey, pz - ez
    n = max(8, int(math.sqrt(dx * dx + dy * dy + dz * dz) / 0.1))
    for i in range(1, n):
        f = i / n
        cx, cy, cz = ex + dx * f, ey + dy * f, ez + dz * f
        cell = (math.floor(cx), math.floor(cy), math.floor(cz))
        if cell == target:
            continue
        if cell in solid or (floor_y is not None and cell[1] < floor_y):
            return False
    return True


def candidate_faces(target: tuple[int, int, int], pos: dict[str, float],
                    first: str) -> list[str]:
    """`first`, then the horizontal face nearest the avatar, then the rest."""
    order = [first]
    dx, dz = target[0] + 0.5 - pos["x"], target[2] + 0.5 - pos["z"]
    if abs(dx) >= abs(dz):
        near = "west" if dx > 0 else "east"      # the face on the avatar's side
    else:
        near = "north" if dz > 0 else "south"
    for f in (near, "below", "north", "south", "west", "east", "above"):
        if f not in order:
            order.append(f)
    return order


# -- the place / use machine (shared by _useat and _build) ---------------------

def new_use_state(target: tuple[int, int, int], item: str | None, face: str,
                  mode: str, hold: int, label: str, tol: float = AIM_TOL,
                  faces: list[str] | None = None) -> dict[str, Any]:
    return {"target": [int(v) for v in target], "item": item, "faces": faces,
            "face": face, "asked": face, "mode": mode, "hold": max(1, int(hold)),
            "label": label, "phase": "aim", "t": 0, "base_use": None, "base_inv": None,
            "tries": 0, "gui0": None, "pos0": None, "tol": float(tol), "aim_off": None}


def _use_gain(agent, st: dict[str, Any]) -> float:
    item = st.get("item")
    if item:
        return agent.stat_now("use_item", item) - float(st["base_use"])
    # No item named: any use_item bucket moving counts.
    raw = (agent.ledger._prev or {}).get("use_item")
    if not isinstance(raw, dict):
        return 0.0
    now = sum(float(v.item()) if hasattr(v, "item") else float(v) for v in raw.values())
    return now - float(st["base_use"])


def _mainhand_damage(agent) -> float | None:
    """Durability used on the held item -- a tool that acted on a block (shears on a
    pumpkin, a hoe on grass) takes 1 damage even when no statistic moves and no count
    changes (a staged scene: shearing a pumpkin left use_item and the inventory
    untouched; the seeds it dropped lay two blocks away)."""
    eq = (agent.ledger._prev or {}).get("equipped_items")
    hand = eq.get("mainhand") if isinstance(eq, dict) else None
    if not isinstance(hand, dict):
        return None
    v = hand.get("damage")
    try:
        return float(v.item()) if hasattr(v, "item") else float(v)
    except (TypeError, ValueError):
        return None


def _use_total(agent) -> float:
    raw = (agent.ledger._prev or {}).get("use_item")
    if not isinstance(raw, dict):
        return 0.0
    return sum(float(v.item()) if hasattr(v, "item") else float(v) for v in raw.values())


def use_step(agent, st: dict[str, Any], mk_act) -> tuple[str, dict[str, Any] | None]:
    """One tick of aim -> click -> verify. Returns (status, action): status is "run"
    (action to send), "done" or "failed" (the note is in st["note"])."""
    pos = agent._cur_pos
    if pos is None:
        return "run", mk_act()
    target = tuple(st["target"])
    if not st.get("started"):
        st["started"] = True
        if st["faces"] is None:
            st["faces"] = candidate_faces(target, pos, st["face"])
        if st["faces"] and st["faces"][0] == st["face"]:
            st["faces"].pop(0)              # the asked face comes first; the rest wait
        if st["mode"] == "place" and overlaps_player(target, pos):
            st["note"] = (f"{st['label']}: the block at {target} is where YOU stand "
                          f"(hitbox overlap); step aside one block, then call it again.")
            return "failed", None
    if st["phase"] == "aim":
        point = aim_point(target, st["face"], 0.5 if st["mode"] == "place" else 0.45)
        pitch, yaw, dist = angles_to(pos, point)
        if dist > REACH:
            st["note"] = (f"{st['label']}: {target} is {dist:.1f} blocks from your eye "
                          f"-- out of reach (max {REACH}). go_to within 3 blocks of it.")
            return "failed", None
        dp = pitch - pos["pitch"]
        dy = norm_yaw_delta(yaw, pos["yaw"])
        st["t"] += 1
        tol = float(st.get("tol", AIM_TOL))
        if (abs(dp) <= tol and abs(dy) <= tol) or st["t"] > AIM_TICKS + 6:
            # A click before the aim settled lands on whatever the crosshair crossed;
            # the note says so, with how far off it was.
            st["aim_off"] = (None if abs(dp) <= tol and abs(dy) <= tol
                             else round(max(abs(dp), abs(dy)), 1))
            st["phase"], st["t"] = "click", 0
            if st["base_use"] is None:
                st["base_use"] = (agent.stat_now("use_item", st["item"]) if st["item"]
                                  else _use_total(agent))
                st["base_inv"] = dict(agent._cur_inv)
                st["gui0"] = bool(agent._gui_open)
                st["pos0"] = (pos["x"], pos["y"], pos["z"])
                st["dmg0"] = _mainhand_damage(agent)
            return "run", mk_act()
        return "run", mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    if st["phase"] == "click":
        t = st["t"]
        st["t"] += 1
        if t < st["hold"]:
            return "run", mk_act(use=1)
        if t < st["hold"] + 2:
            return "run", mk_act()
        st["phase"], st["t"] = "verify", 0
    # verify
    gained = _use_gain(agent, st)
    inv_delta = {k: agent._cur_inv.get(k, 0) - st["base_inv"].get(k, 0)
                 for k in set(agent._cur_inv) | set(st["base_inv"])
                 if agent._cur_inv.get(k, 0) != st["base_inv"].get(k, 0)}
    if st["mode"] == "place":
        ok = gained >= 1
    else:
        moved = (st["pos0"] is not None and pos is not None and
                 math.dist(st["pos0"], (pos["x"], pos["y"], pos["z"])) > 0.6)
        item = st.get("item")
        # The held item's own count moving (a bucket swapping, seeds sown, a bed placed)
        # is evidence; a stray pickup of something else is not.
        own = bool(item) and any(
            (k == item or k.endswith("bucket") and "bucket" in item) and v != 0
            for k, v in inv_delta.items())
        dmg = _mainhand_damage(agent)
        worn = (st.get("dmg0") is not None and dmg is not None and dmg > st["dmg0"])
        ok = (gained >= 1 or own or worn or (bool(agent._gui_open) and not st["gui0"])
              or moved)
        if ok and worn and not (gained >= 1 or own):
            st["worn"] = True
    if ok:
        st["gained"], st["inv_delta"] = gained, inv_delta
        return "done", None
    st["t"] += 1
    if st["t"] <= VERIFY_TICKS:
        return "run", mk_act()
    st["tries"] += 1
    if st["faces"] and st["tries"] < 3:
        st["face"], st["phase"], st["t"] = st["faces"].pop(0), "aim", 0
        return "run", mk_act()
    what = ("did not go down" if st["mode"] == "place" else "had no visible effect")
    st["note"] = (f"{st['label']}: the {st['item'] or 'held item'} {what} at {target} after "
                  f"{st['tries']} face(s) ({st['face']} last): use_item unchanged"
                  + (", inventory unchanged" if not inv_delta else "")
                  + (". The target spot is probably occupied, or nothing solid stands on "
                     "the side being clicked; name another `face`, or the block next to it."
                     if st["mode"] == "place" else
                     ". Check what you hold and what the block is; the item may not act on it."))
    return "failed", None


def _hotbar_of(info: dict, item: str) -> int | None:
    for s, _q in gui.find_slots(info, item):
        if s <= 8:
            return s
    return None


# -- single use / place -------------------------------------------------------

def _prep_item(cur, info: dict, item: str | None, label: str
               ) -> tuple[list[dict[str, Any]], str]:
    """One entry that puts `item` in the hotbar and selects it; ([], err) when impossible.

    Whether it is possible is decided here, against the inventory the plan was made
    from. HOW is decided when the entry runs (`_prep_tick`): every entry of a plan is
    expanded before the first one runs, and an earlier entry's inventory trip moves
    stacks. One life's `place_at(cobblestone)` swapped the cobblestone into the hotbar
    slot of its obsidian; the `pillar_up(item=cobblestone)` behind it had been compiled
    from the same picture, so its own trip swapped the two back, selected the slot, and
    the pillar went up in the life's last three obsidian."""
    from mcu_worldmodel import macros_gui as MG
    from mcu_worldmodel import procedures as P

    if not item:
        return [], ""
    stacks = gui.find_slots(info, item)
    if not stacks:
        return [], f"{label}: you carry no {item}."
    acts, hot, err = MG.ensure_hotbar(cur, info, item, label)
    if err:
        return [], err
    acts = acts + P.equip_hotbar(hot + 1)
    cost = sum(max(0, int(a.get("_cost", 1))) for a in acts)
    return [macros.marker("_prep", {"item": item, "label": label}, cost)], ""


@macros.tick("_prep")
def _prep_tick(agent, pp: dict[str, Any], mk_act):
    """`_prep_item` at run time: the trip and the selection compiled against the
    inventory of THIS tick and spliced in behind the marker, under the same plan entry
    (as `_later` does). If the item cannot be brought to hand any more, the rest of the
    plan is dropped with the reason: what follows would act with whatever is selected."""
    from mcu_worldmodel import macros_gui as MG
    from mcu_worldmodel import procedures as P

    item, label = str(pp.get("item", "")), str(pp.get("label", "item"))
    info = agent._cur_info or {}
    if gui.find_slots(info, item):
        acts, hot, err = MG.ensure_hotbar(agent.cursor.copy(), info, item, label)
    else:
        acts, hot, err = [], -1, (f"{label}: you carry no {item} any more -- an earlier "
                                  f"entry of this plan used it up or moved it.")
    if err:
        agent._note_failure(label.split("(")[0])
        agent._flush_tail(f"{err} Nothing was done with another item in its place.",
                          "prep_item_flush")
        return None
    idx = agent.queue[0][1] if agent.queue else 0
    for step in reversed(acts + P.equip_hotbar(hot + 1)):
        agent.queue.insert(1, (step, idx))
    return None


def use_at(cur, info: dict, x: float = 0.0, y: float = 0.0, z: float = 0.0,
           item: str | None = None, face: str = "below", hold: int = 1
           ) -> tuple[list[dict[str, Any]], str]:
    """Right-click a face of the block at (x, y, z) with `item` selected."""
    return _use_or_place(cur, info, x, y, z, item, face, hold, "use")


def place_at(cur, info: dict, x: float = 0.0, y: float = 0.0, z: float = 0.0,
             item: str | None = None, face: str = "below"
             ) -> tuple[list[dict[str, Any]], str]:
    """Put `item` INTO the block cell (x, y, z), clicking the named face of its support."""
    if not item:
        return [], "place_at: name the block to place (item=...)."
    return _use_or_place(cur, info, x, y, z, item, face, 1, "place")


def _use_or_place(cur, info, x, y, z, item, face, hold, mode):
    label = f"{'place_at' if mode == 'place' else 'use_at'}({item or 'hand'})"
    try:
        target = (math.floor(float(x)), math.floor(float(y)), math.floor(float(z)))
    except (TypeError, ValueError):
        return [], f"{label}: bad coordinates {x!r}, {y!r}, {z!r}"
    face = str(face or "below").lower()
    if face not in FACE_OFFSET:
        return [], f"{label}: face must be one of {', '.join(FACE_OFFSET)}, not {face!r}"
    if item and mode == "place" and _is_nonplaceable(item):
        return [], (f"{label}: {item} is not a block; use_at() uses an item on a block, "
                    f"place_at() puts a block down.")
    acts, err = _prep_item(cur, info, item, label)
    if err:
        return [], err
    st = new_use_state(target, item, face, mode, hold, label)
    acts.append(macros.marker("_useat", st, AIM_TICKS + hold + 2 + VERIFY_TICKS * 3 + 4))
    return acts, (f"{label} at {target}, {face} face"
                  + (f", holding use {hold} ticks" if hold > 1 else ""))


def _is_nonplaceable(item: str) -> bool:
    return any(w in item for w in ("pickaxe", "sword", "axe", "shovel", "hoe", "bucket",
                                   "flint_and_steel", "shears", "bow", "arrow", "rod",
                                   "lead", "potion", "bottle", "ingot", "stick", "seeds",
                                   "bone_meal", "map", "compass", "spyglass", "food"))


@macros.tick("_useat", shrink=None)
def _useat_tick(agent, st: dict[str, Any], mk_act):
    opened = bool(agent._gui_open) and st.get("gui0") is False   # by this call's click
    if agent._gui_open and not opened:
        agent._flush_tail(f"{st['label']}: a screen is open; the world click would do "
                          f"nothing. close_inventory first.", "useat_gui_flush")
        return None
    if opened:
        st["phase"] = "verify"
    status, action = use_step(agent, st, mk_act)
    if status == "run":
        return action
    if status == "done":
        d = st.get("inv_delta") or {}
        dtxt = ", ".join(f"{k} {v:+d}" for k, v in sorted(d.items())) or "no inventory change"
        agent.cursor_stats["useat_ok"] = agent.cursor_stats.get("useat_ok", 0) + 1
        # The verification is the use_item count: it proves a block went down, not
        # that it went into the target. A fallback face or an unsettled aim is where
        # the stray blocks of the recorded portal frames came from, so both are named.
        doubt = ""
        if st.get("asked") and st["face"] != st["asked"]:
            doubt += (f"; NOT the {st['asked']} face you named -- the block may sit in a "
                      f"neighbouring cell, look at {tuple(st['target'])} before building on it")
        if st.get("aim_off"):
            doubt += (f"; clicked {st['aim_off']:g} degrees off the aim -- "
                      f"check which block took it")
        agent.memory.add_note(
            f"{st['label']}: {'placed' if st['mode'] == 'place' else 'used'} at "
            f"{tuple(st['target'])} ({st['face']} face) -- use_item +{st.get('gained', 0):g}, "
            f"{dtxt}" + (" (the tool took wear: it acted on the block)" if st.get("worn")
                         else "") + ("; its screen is open" if opened else "") + doubt + ".")
        return None
    agent._note_failure(st["label"].split("(")[0])
    agent._flush_tail(st.get("note", f"{st['label']} failed"), "useat_failed_flush")
    return None


# -- closed-loop look at a world point ------------------------------------------

def look_at_point(x: float, y: float, z: float, ticks: int = 20,
                  tol: float = AIM_TOL) -> list[dict[str, Any]]:
    """Steer the crosshair onto the WORLD point (x, y, z) from the live position each
    tick (procedures.look_at computes its deltas once, at plan time -- a push from
    flowing water between planning and execution left mine_obsidian swinging at the
    sky, a staged scene)."""
    t = max(4, min(60, int(ticks)))
    return [macros.marker("_lookat", {"x": float(x), "y": float(y), "z": float(z),
                                      "t": 0, "n": t, "tol": float(tol)}, t)]


@macros.tick("_lookat", shrink="n")
def _lookat_tick(agent, la: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    pitch, yaw, _ = angles_to(pos, (la["x"], la["y"], la["z"]))
    dp = pitch - pos["pitch"]
    dy = norm_yaw_delta(yaw, pos["yaw"])
    if abs(dp) <= la["tol"] and abs(dy) <= la["tol"]:
        return None
    la["t"] += 1
    if la["t"] > la["n"]:
        agent.memory.add_note(
            f"look_at: still {dp:.1f}/{dy:.1f} degrees off ({la['x']:.1f}, {la['y']:.1f}, "
            f"{la['z']:.1f}) after {la['n']} ticks.")
        return None
    return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])


# -- hold / throw / eat --------------------------------------------------------

def use_held(cur, info: dict, item: str | None = None, hold: int = 32
             ) -> tuple[list[dict[str, Any]], str]:
    """Select `item` (or keep what is held) and hold `use` for `hold` ticks, then release."""
    label = f"use_held({item or 'held'})"
    acts, err = _prep_item(cur, info, item, label)
    if err:
        return [], err
    h = max(1, min(200, int(hold)))
    acts.append(macros.marker("_usehold", {"item": item, "hold": h, "n": 1, "gap": 4,
                                           "t": 0, "done": 0, "label": label,
                                           "base_use": None, "base_inv": None}, h + 8))
    return acts, f"{label}: holding use for {h} ticks"


def throw(cur, info: dict, item: str = "snowball", n: int = 1
          ) -> tuple[list[dict[str, Any]], str]:
    """Tap `use` with a throwable selected, `n` times (snowball, egg, ender pearl...)."""
    label = f"throw({item})"
    acts, err = _prep_item(cur, info, item, label)
    if err:
        return [], err
    n = max(1, min(16, int(n)))
    acts.append(macros.marker("_usehold", {"item": item, "hold": 1, "n": n, "gap": 6,
                                           "t": 0, "done": 0, "label": label,
                                           "base_use": None, "base_inv": None}, n * 9 + 6))
    return acts, f"{label} x{n}"


def eat(cur, info: dict, item: str | None = None) -> tuple[list[dict[str, Any]], str]:
    """Eat: hold use ~40 ticks on a food (the best one carried when unnamed)."""
    if not item:
        for f in FOODS:
            if gui.find_slots(info, f):
                item = f
                break
        if not item:
            return [], "eat: you carry no food (bread, cooked meat, apple...)."
    acts, err = _prep_item(cur, info, item, "eat")
    if err:
        return [], err
    acts.append(macros.marker("_usehold", {"item": item, "hold": 40, "n": 1, "gap": 4,
                                           "t": 0, "done": 0, "label": f"eat({item})",
                                           "base_use": None, "base_inv": None}, 48))
    return acts, f"eating {item} (food is {'full' if _food(info) >= 20 else 'not full'})"


def _food(info: dict) -> float:
    v = info.get("food_level")
    try:
        return float(v.item()) if hasattr(v, "item") else float(v)
    except (TypeError, ValueError):
        return 0.0


@macros.tick("_usehold")
def _usehold_tick(agent, uh: dict[str, Any], mk_act):
    if agent._gui_open:
        agent._flush_tail(f"{uh['label']}: a screen is open; close it first.",
                          "usehold_gui_flush")
        return None
    if uh["base_use"] is None:
        uh["base_use"] = (agent.stat_now("use_item", uh["item"]) if uh["item"]
                          else _use_total(agent))
        uh["base_inv"] = dict(agent._cur_inv)
    t = uh["t"]
    cycle = uh["hold"] + uh["gap"]
    if uh["done"] < uh["n"]:
        uh["t"] += 1
        if t % cycle < uh["hold"]:
            return mk_act(use=1)
        if t % cycle == cycle - 1:
            uh["done"] += 1
        return mk_act()
    # settle, then verify
    if t < uh["n"] * cycle + 4:
        uh["t"] += 1
        return mk_act()
    gained = ((agent.stat_now("use_item", uh["item"]) - uh["base_use"]) if uh["item"]
              else _use_total(agent) - uh["base_use"])
    d = {k: agent._cur_inv.get(k, 0) - uh["base_inv"].get(k, 0)
         for k in set(agent._cur_inv) | set(uh["base_inv"])
         if agent._cur_inv.get(k, 0) != uh["base_inv"].get(k, 0)}
    dtxt = ", ".join(f"{k} {v:+d}" for k, v in sorted(d.items()))
    if gained >= 1 or d:
        agent.cursor_stats["usehold_ok"] = agent.cursor_stats.get("usehold_ok", 0) + 1
        agent.memory.add_note(f"{uh['label']}: use_item +{gained:g}"
                              + (f", {dtxt}" if dtxt else "") + ".")
    else:
        agent._note_failure(uh["label"].split("(")[0])
        agent.memory.add_note(
            f"{uh['label']}: nothing registered (use_item unchanged, inventory "
            f"unchanged). A bow needs >= 25 ticks of hold before release; food needs "
            f"the food bar below 20; a throwable needs to be the SELECTED hotbar item.")
    return None


# -- fill a bucket at water you can see -----------------------------------------
#
# Why closed-loop. use_at(bucket) needs the exact water cell AND the right face; the model
# reads neither off a frame (two runs: three use_at calls at
# guessed cells, "no visible effect" each time, then 260 ticks of scanning). A bucket fills
# from any still source block under the crosshair within reach, so the runner sweeps the
# crosshair over the ground ahead with the bucket held and taps use at each aim until the
# inventory shows a filled bucket. Verified on the inventory (water_bucket / lava_bucket /
# milk_bucket: whatever the sweep met is named).

#: Measured on this engine (probe, eye 1.62 above the feet, a source 3 blocks
#: ahead at feet level): a one-tick use fills at pitch 15-30 and not at 10 or 35. Nearer
#: water wants a steeper aim (2 ahead: ~17-33; the next cell: ~26-58; water a block below
#: the shore: steeper still). At a natural pond's bank the water IS a block below: at
#: one run's shore pose pitch 35 and 45 filled nothing and 55/65
#: filled (the sweep's steep aim is 60, between them), so the sweep runs every pitch at one
#: heading before widening -- the model faces
#: the water it saw, and one run's 140-tick budget (15 aims) had ended before the first steep
#: aim of the old pitch-major order.
FILLB_PITCHES = (25.0, 35.0, 45.0, 60.0, 18.0)
FILLB_YAWS = (0.0, -20.0, 20.0, -40.0, 40.0)
FILLB_AIM_TOL = 3.0
FILLB_HOLD = 2
FILLB_SETTLE = 4


def fill_bucket(cur, info: dict, ticks: int = 260) -> tuple[list[dict[str, Any]], str]:
    """Hold the empty bucket and sweep the crosshair over the ground ahead, tapping use at
    each aim, until a filled bucket appears in the inventory."""
    label = "fill_bucket"
    acts, err = _prep_item(cur, info, "bucket", label)
    if err:
        return [], err
    n = max(60, min(400, int(ticks)))
    aims = [(p, y) for y in FILLB_YAWS for p in FILLB_PITCHES]
    acts.append(macros.marker("_fillb", {"aims": aims, "k": 0, "t": 0, "n": n, "yaw0": None,
                                         "phase": "aim", "hold": 0, "base_inv": None,
                                         "label": label}, n))
    return acts, (f"{label}: sweeping the crosshair over the ground ahead with the bucket "
                  f"held (pitch 25-60 and 18 at each of yaw 0, +-20, +-40), tapping use until "
                  f"it fills, up to {n} ticks")


def _filled_buckets(agent, base: dict[str, int]) -> dict[str, int]:
    return {k: agent._cur_inv.get(k, 0) - base.get(k, 0) for k in agent._cur_inv
            if k.endswith("_bucket") and agent._cur_inv.get(k, 0) > base.get(k, 0)}


@macros.tick("_fillb", shrink="n")
def _fillb_tick(agent, fb: dict[str, Any], mk_act):
    if agent._gui_open:
        agent._flush_tail(f"{fb['label']}: a screen is open; close it first.",
                          "fillb_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    if fb["base_inv"] is None:
        fb["base_inv"] = dict(agent._cur_inv)
        fb["yaw0"] = float(pos["yaw"])
    got = _filled_buckets(agent, fb["base_inv"])
    if got:
        name = sorted(got)[0]
        agent.cursor_stats["fillb_ok"] = agent.cursor_stats.get("fillb_ok", 0) + 1
        agent.memory.add_note(
            f"{fb['label']}: the bucket filled -- {name} +{got[name]} (aim {fb['k'] + 1} of "
            f"{len(fb['aims'])}, pitch {pos['pitch']:.0f} yaw {norm_yaw(pos['yaw']):.0f}, "
            f"{fb['t']} ticks). You now carry {agent._cur_inv.get(name, 0)} {name}.")
        return None
    fb["t"] += 1
    if fb["t"] > fb["n"] or fb["k"] >= len(fb["aims"]):
        agent._note_failure(fb["label"])
        pressed = ", ".join(f"{p}/{y}" for p, y in fb.get("pressed", [])[:20])
        agent.memory.add_note(
            f"{fb['label']}: nothing filled in {fb['k']} aims / {fb['t']} ticks (pressed use "
            f"at pitch/yaw {pressed}): no still water within reach of the sweep. Stand "
            f"at the shore with the water 1-3 blocks ahead and below the eye, then call it "
            f"again; a bucket fills only from a SOURCE block (still water), never from the "
            f"flowing part of a stream.")
        return None
    p_t, y_off = fb["aims"][fb["k"]]
    if fb["phase"] == "aim":
        dp = p_t - float(pos["pitch"])
        dy = norm_yaw_delta(fb["yaw0"] + y_off, float(pos["yaw"]))
        if abs(dp) <= FILLB_AIM_TOL and abs(dy) <= FILLB_AIM_TOL:
            fb["phase"] = "use"
            fb["hold"] = 0
            fb.setdefault("pressed", []).append((round(float(pos["pitch"])),
                                                 round(norm_yaw(float(pos["yaw"])))))
            return mk_act(use=1)
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    fb["hold"] += 1
    if fb["hold"] < FILLB_HOLD:
        return mk_act(use=1)
    if fb["hold"] >= FILLB_HOLD + FILLB_SETTLE:
        fb["k"] += 1
        fb["phase"] = "aim"
    return mk_act()


# -- fetch water: find it, walk to the shore, fill --------------------------------------
# Two runs: a pond 10 blocks away behind
# spruce leaves; go_to stopped "blocked" 6 blocks short twice, harvest_tree saw no trunk,
# fill_bucket swept 36 aims at nothing, and the governor refused a third call -- 400
# steps at the crafting table with the bucket in hand. The model can see the water and
# cannot get to it: no macro walked toward a THING in the frame through the leaves.
# This one does: it looks around for the blue of still water (vision.water_view), walks
# toward the mass correcting the heading on every frame, breaks what stops the walk
# (leaves and dirt; a trunk is sidestepped), stops at the shore (the pool fills the
# lower-centre window, or the feet went into it) and runs fill_bucket there.

#: The walk's pitch: far water (a 8-degree depression at 12 blocks) and the shore (a
#: 30-40 degree depression at 2-3 blocks) both fit a 70-degree view pitched 15 down.
FETCHW_PITCH = 15.0
#: The scan's pitch and headings: 12 views 30 degrees apart, like scan_around.
FETCHW_SCAN_PITCH = 12.0
FETCHW_SCAN_STEPS = 12
#: The horizontal view (~102 degrees at FOV 70 on 16:9, the tree world's measurement):
#: a mass at half the frame's width from the crosshair is ~51 degrees off.
FETCHW_HFOV = 102.0
#: Ticks of attack for one blocking block: leaves take 6 by hand, dirt/grass/sand 15,
#: a log 60 (by hand: no axe in the dragon kit) -- a trunk is walked around instead.
FETCHW_CLEAR = 45
#: A lava lake on the surface: the walk stops rather than sprint-jump into it.
FETCHW_LAVA_STOP = 0.05
#: Water filling this share of the lower view is a few blocks off: the walk drops the hop.
FETCHW_NEAR_FRAC = 0.05


#: Under this many ticks fetch_water does not start (the scan alone is ~100, the walk 100+).
FETCHW_MIN_TICKS = 250


def fetch_water(cur, info: dict, n: int = 600) -> tuple[list[dict[str, Any]], str]:
    """Look around for still water, walk to its shore breaking the leaves in the way,
    and run fill_bucket there."""
    label = "fetch_water"
    if not gui.find_slots(info, "bucket"):
        return [], f"{label}: you carry no empty bucket (the sweep at the shore needs one)."
    n = max(FETCHW_MIN_TICKS, min(1200, int(n)))     # a small model-chosen n is raised, not refused
    st = {"label": label, "n": n, "t": 0, "phase": "look", "phase_t": 0, "yaw0": None,
          "scan": [], "k": 0, "scans": 0, "target": None, "seen_t": 0, "last": None,
          "stuck": 0, "clears": 0, "cleared": 0, "side": 0, "x0": None, "z0": None}
    acts = [macros.marker("_fetchw", st, n)]
    acts[0]["_min"] = FETCHW_MIN_TICKS          # whole or not at all (procedures.shrink_marker)
    return acts, (f"{label}: looking for still water (the blue in the lower view), then "
                  f"walking to its shore through leaves and running fill_bucket there, "
                  f"up to {n} ticks")


def _fetchw_finish(agent, st: dict[str, Any], why: str, ok: bool) -> None:
    pos = agent._cur_pos or {}
    walked = (math.hypot(float(pos.get("x", 0.0)) - st["x0"], float(pos.get("z", 0.0)) - st["z0"])
              if st["x0"] is not None and pos else 0.0)
    where = (f"({pos['x']:.0f}, {pos['y']:.0f}, {pos['z']:.0f})" if pos else "?")
    agent.cursor_stats["fetchw_blocks"] = agent.cursor_stats.get("fetchw_blocks", 0) + int(walked)
    if ok:
        agent.cursor_stats["fetchw_ok"] = agent.cursor_stats.get("fetchw_ok", 0) + 1
        acts, err = fill_bucket(agent.cursor.copy(), agent._cur_info or {})
        tail = ""
        if not acts:
            tail = f" The sweep could not start: {err}"
        else:
            idx = agent.queue[0][1] if agent.queue else 0
            for step in reversed(acts):
                agent.queue.insert(1, (step, idx))
            tail = " The bucket sweep (fill_bucket) runs next."
        agent.memory.add_note(
            f"{st['label']}: water reached at {where} after {st['t']} ticks and "
            f"{walked:.0f} blocks ({why}"
            + (f"; {st['cleared']} block(s) broken on the way" if st["cleared"] else "")
            + ")." + tail)
    else:
        agent._note_failure(st["label"])
        agent.memory.add_note(
            f"{st['label']}: stopped at {where} after {st['t']} ticks and {walked:.0f} "
            f"blocks -- {why}")


def _fetchw_measure(agent, pitch: float) -> tuple[float, float, float, float]:
    """(fraction, cx, bottom, near) of the water in the current frame, measured from one
    degree below the horizon: at pitch 12 that is the 34% line, at pitch 15 the 30% --
    the fixed 35% cut lost every pool beyond 30 blocks to the walk (audit pass 16)."""
    frame = agent._last_pov
    if frame is None:
        return 0.0, 0.0, 0.0, 0.0
    arr = np.asarray(frame)
    rows_from = min(0.55, max(0.25, 0.5 - float(pitch) / 70.0 + 0.012))
    frac, cx, bottom = vision.water_view(arr, rows_from=rows_from)
    return frac, cx, bottom, vision.water_near(arr)


def _fetchw_walk(st: dict[str, Any]) -> None:
    """Enter the walk: the sight clock starts NOW (a walk that began after a 180-tick
    scan read "lost sight for 80 ticks" on its first tick -- audit pass 16)."""
    st["phase"], st["phase_t"], st["stuck"], st["last"] = "walk", 0, 0, None
    st["seen_t"] = st["t"]
    st["progress"] = 0


@macros.tick("_fetchw", shrink="n", moving=True)
def _fetchw_tick(agent, st: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail(f"{st['label']}: a screen is open; close it first.",
                          "fetchw_gui_flush")
        return None
    if pos is None:
        return mk_act()
    if st["x0"] is None:
        st["x0"], st["z0"], st["yaw0"] = float(pos["x"]), float(pos["z"]), float(pos["yaw"])
        if st["n"] < FETCHW_MIN_TICKS:
            # only the runner's step-cap shrink gets here (the compile raises a small n
            # to FETCHW_MIN_TICKS): three arms spent 100-200 leftover
            # ticks on a scan that could not end in a walk. Say so and let the next
            # plan lead with it.
            agent.cursor_stats["fetchw_not_started"] = (
                agent.cursor_stats.get("fetchw_not_started", 0) + 1)
            _fetchw_finish(agent, st, f"NOT STARTED: only {st['n']} ticks were available "
                                      f"(the plan's remaining budget) and the search needs "
                                      f"{FETCHW_MIN_TICKS}+ -- a 12-heading scan, then the "
                                      f"walk. Put fetch_water FIRST in the next plan.", ok=False)
            return None
    st["t"] += 1
    if st["t"] > st["n"]:
        _fetchw_finish(agent, st, "the tick budget ran out before the shore; call it again "
                                  "from here, or go_to a point you can name.", ok=False)
        return None
    ph = st["phase"]
    frac, cx, bottom, near = _fetchw_measure(agent, float(pos["pitch"]))

    if ph == "look":
        # pitch down first: the water lies below the horizon
        dp = FETCHW_PITCH - float(pos["pitch"])
        st["phase_t"] += 1
        if abs(dp) > 3.0 and st["phase_t"] <= 6:
            return mk_act(camera=[max(-30.0, min(30.0, dp)), 0.0])
        if st["phase_t"] <= 7:
            return mk_act()                            # one tick for the frame
        if frac >= vision.WATER_SEEN:
            _fetchw_walk(st)
            return mk_act()
        st["phase"], st["phase_t"], st["k"], st["scan"] = "scan", 0, 0, []
        st["scans"] += 1
        return mk_act()

    if ph == "scan":
        steps = FETCHW_SCAN_STEPS
        if st["k"] >= steps:
            best = max(st["scan"], key=lambda e: e[0]) if st["scan"] else None
            if best is None or best[0] < vision.WATER_SEEN:
                _fetchw_finish(agent, st, f"no still water in view from here in {steps} "
                                          f"headings (the largest reading {100 * (best[0] if best else 0.0):.1f}% "
                                          f"of the lower view). Travel toward where the map or a "
                                          f"scan sheet shows water, or dig for a spring, then "
                                          f"call it again.", ok=False)
                return None
            st["target"] = norm_yaw(best[1] + best[2] * FETCHW_HFOV)
            st["phase"], st["phase_t"] = "turn", 0
            return mk_act()
        target_yaw = st["yaw0"] + 360.0 * st["k"] / steps
        dy = norm_yaw_delta(target_yaw, float(pos["yaw"]))
        dp = FETCHW_SCAN_PITCH - float(pos["pitch"])
        st["phase_t"] += 1
        if (abs(dy) > 2.0 or abs(dp) > 2.0) and st["phase_t"] <= 12:
            return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
        if st["phase_t"] <= 13:
            return mk_act()                            # settle: the frame catches up
        st["scan"].append((frac, float(pos["yaw"]), cx))
        st["k"] += 1
        st["phase_t"] = 0
        return mk_act()

    if ph == "turn":
        dy = norm_yaw_delta(st["target"], float(pos["yaw"]))
        dp = FETCHW_PITCH - float(pos["pitch"])
        st["phase_t"] += 1
        if (abs(dy) > 3.0 or abs(dp) > 3.0) and st["phase_t"] <= 12:
            return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
        _fetchw_walk(st)
        return mk_act()

    if ph == "clear":
        # attack the block ahead: eye level first (then a jump clears a one-high rest),
        # the foot block from the second try on
        st["phase_t"] += 1
        p_t = 0.0 if st["clears"] % 2 == 1 else 55.0
        dp = p_t - float(pos["pitch"])
        if abs(dp) > 3.0 and st["phase_t"] <= 4:
            return mk_act(camera=[max(-30.0, min(30.0, dp)), 0.0])
        if st["phase_t"] <= FETCHW_CLEAR + 4:
            return mk_act(attack=1)
        st["cleared"] += 1
        _fetchw_walk(st)
        return mk_act()

    if ph == "side":
        # a trunk (or a rock) the clears did not remove: strafe past it
        st["phase_t"] += 1
        if st["phase_t"] <= 14:
            return mk_act(left=1, jump=1) if st["side"] % 2 == 1 else mk_act(right=1, jump=1)
        _fetchw_walk(st)
        return mk_act()

    # walk
    st["phase_t"] += 1
    if near >= vision.WATER_NEAR or (frac >= 0.10 and bottom >= 0.86):
        _fetchw_finish(agent, st, f"the water fills {100 * near:.0f}% of the lower-centre "
                                  f"view" + (", down to the frame's bottom edge"
                                             if bottom >= 0.86 else ""), ok=True)
        return None
    lava = (vision.lava_fraction(np.asarray(agent._last_pov))
            if agent._last_pov is not None else 0.0)
    if lava >= FETCHW_LAVA_STOP:
        _fetchw_finish(agent, st, f"LAVA ahead ({100 * lava:.0f}% of the lower view): the "
                                  f"walk stopped short of it. Find water in another direction.",
                       ok=False)
        return None
    if frac >= vision.WATER_SEEN:
        st["seen_t"] = st["t"]
        dyaw = cx * FETCHW_HFOV
    else:
        dyaw = 0.0
        if st["t"] - st["seen_t"] > 80:
            if st["scans"] < 2:
                st["phase"], st["phase_t"], st["k"], st["scan"] = "scan", 0, 0, []
                st["scans"] += 1
                st["yaw0"] = float(pos["yaw"])
                return mk_act()
            _fetchw_finish(agent, st, "lost sight of the water for 80 ticks and a second "
                                      "scan found none; call it again from higher ground "
                                      "or nearer the place the scan sheet showed it.",
                           ok=False)
            return None
    dp = FETCHW_PITCH - float(pos["pitch"])
    last = st["last"]
    moved = (math.hypot(float(pos["x"]) - last[0], float(pos["z"]) - last[1])
             if last is not None else None)
    st["last"] = (float(pos["x"]), float(pos["z"]))
    if moved is not None and moved < 0.03:
        st["stuck"] += 1
        if st["stuck"] >= 3:
            st["clears"] += 1
            if st["clears"] > 4:
                _fetchw_finish(agent, st, "the way is blocked and four clears and two "
                                          "side-steps did not open it; route around on foot.",
                               ok=False)
                return None
            if st["clears"] in (3, 4):
                st["side"] += 1
                st["phase"], st["phase_t"] = "side", 0
                return mk_act()
            st["phase"], st["phase_t"] = "clear", 0
            return mk_act()
    else:
        st["stuck"] = 0
        if moved is not None:
            st["progress"] = st.get("progress", 0) + 1
            if st["progress"] >= 20:          # 20 moving ticks: the obstacle is behind
                st["clears"], st["side"] = 0, 0
    if abs(dyaw) > 20.0:
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dyaw))])
    # The hop (a one-block step) stays on until the water is near: airborne the eye sits
    # a block higher and the shore test's window looks past the pool -- a staged scene
    # sprint-hopped 4 blocks past the shore into the water.
    hop = 1 if frac < FETCHW_NEAR_FRAC or st["stuck"] else 0
    return mk_act(forward=1, sprint=1, jump=hop,
                  camera=[max(-10.0, min(10.0, dp)), max(-8.0, min(8.0, dyaw))])


# -- pillar up -------------------------------------------------------------------

#: `watch(until, n)`: the conditions the runner can end a watch on, from the game's
#: own numbers (no pixels): "none" (just n ticks), "inventory" (any count changes),
#: "gui" (a screen opens), "health" (health changes), "damage" (health falls),
#: "y_below:<v>", "y_above:<v>", "moved:<blocks>" (from where the watch began).
WATCH_UNTIL = ("none", "inventory", "gui", "health", "damage", "y_below", "y_above", "moved")


def watch(until: str = "none", n: int = 60) -> list[dict[str, Any]]:
    """Do nothing for up to `n` ticks and stop the moment `until` holds -- the observe
    step between acting and deciding (wz1119's `watch` samples pixels; this reads the
    game's numbers). With `until="none"` it is a plain wait: the water settles, a mob
    comes into view, a drop lands."""
    n = max(1, min(400, int(n)))
    until = str(until or "none").strip().lower()
    key = until.split(":", 1)[0]
    if key not in WATCH_UNTIL:
        raise ValueError(f"watch: unknown until {until!r}; one of {', '.join(WATCH_UNTIL)}")
    if key in ("y_below", "y_above", "moved"):
        try:
            float(until.split(":", 1)[1])
        except (IndexError, ValueError):
            raise ValueError(f"watch: {key} needs a number, e.g. {key}:12")
    return [macros.marker("_watch", {"until": until, "n": n, "t": 0, "start": None}, n)]


@macros.tick("_watch", shrink="n")
def _watch_tick(agent, wt: dict[str, Any], mk_act):
    pos, inv = agent._cur_pos, dict(agent._cur_inv or {})
    info = agent._cur_info or {}
    health = info.get("health")
    if wt.get("start") is None:
        wt["start"] = {"pos": dict(pos) if pos else None, "inv": inv,
                       "health": health, "gui": bool(agent._gui_open)}
    wt["t"] = int(wt.get("t", 0)) + 1
    st = wt["start"]
    until = str(wt["until"])
    key, _, arg = until.partition(":")
    met = None
    if key == "inventory":
        diff = {k: inv.get(k, 0) - st["inv"].get(k, 0) for k in set(inv) | set(st["inv"])
                if inv.get(k, 0) != st["inv"].get(k, 0)}
        if diff:
            met = "inventory changed: " + ", ".join(f"{k} {v:+d}" for k, v in sorted(diff.items()))
    elif key == "gui":
        if agent._gui_open and not st["gui"]:
            met = "a screen opened"
    elif key == "health":
        if health is not None and st["health"] is not None and health != st["health"]:
            met = f"health {st['health']} -> {health}"
    elif key == "damage":
        if health is not None and st["health"] is not None and health < st["health"]:
            met = f"health {st['health']} -> {health}"
    elif key in ("y_below", "y_above") and pos is not None:
        v = float(arg)
        if (key == "y_below" and pos["y"] < v) or (key == "y_above" and pos["y"] > v):
            met = f"y {pos['y']:.1f}"
    elif key == "moved" and pos is not None and st["pos"] is not None:
        d = math.hypot(pos["x"] - st["pos"]["x"], pos["z"] - st["pos"]["z"])
        if d >= float(arg):
            met = f"moved {d:.1f} blocks"
    if met is not None:
        agent.cursor_stats["watch_met"] = agent.cursor_stats.get("watch_met", 0) + 1
        agent.memory.add_note(f"watch(until={until}): {met} after {wt['t']} tick(s).")
        return None
    if wt["t"] >= int(wt["n"]):
        agent.cursor_stats["watch_timeouts"] = agent.cursor_stats.get("watch_timeouts", 0) + 1
        agent.memory.add_note(
            f"watch(until={until}): " + ("waited" if key == "none" else "not met in")
            + f" {wt['n']} tick(s)"
            + ("" if key == "none" else "; the game's numbers did not change that way")
            + ".")
        return None
    return mk_act()


def pillar_up(cur, info: dict, n: int = 3, item: str | None = None
              ) -> tuple[list[dict[str, Any]], str]:
    """Jump and place `n` blocks under the feet (a tower, a lookout, an escape)."""
    n = max(1, min(30, int(n)))
    if not item:
        for b in ("cobblestone", "stone", "dirt", "netherrack", "oak_planks", "stone_bricks",
                  "andesite", "diorite", "granite", "cobbled_deepslate"):
            if gui.find_slots(info, b):
                item = b
                break
        if not item:
            return [], "pillar_up: you carry no placeable block (cobblestone, dirt...)."
    have = sum(q for _, q in gui.find_slots(info, item))
    if have < n:
        return [], f"pillar_up: {n} blocks asked, {have} {item} carried."
    acts, err = _prep_item(cur, info, item, "pillar_up")
    if err:
        return [], err
    budget = n * 24 + 30
    acts.append(macros.marker("_pillar", {"item": item, "target": n, "placed": 0,
                                          "phase": "look", "t": 0, "tries": 0,
                                          "y_jump": None, "budget": budget, "used": 0},
                              budget))
    # The intent, not the result: the count that landed comes from `_pillar_tick` when
    # it ends. One life read the old "4 cobblestone under the feet" after a hit had
    # dropped the plan at one block, and died pillaring on what it took for a fact.
    return acts, (f"pillar_up: placing {n} {item} under the feet; the verified count "
                  f"follows in its own note when it ends")


def _block_counts(agent) -> dict[str, int]:
    """Carried quantity by item type, from the inventory of this tick."""
    out: dict[str, int] = {}
    inv = (getattr(agent, "_cur_info", None) or {}).get("inventory")
    for e in (inv.values() if isinstance(inv, dict) else ()):
        if not isinstance(e, dict) or slot_is_empty(e):
            continue
        q = e.get("quantity", 0)
        out[str(e.get("type"))] = out.get(str(e.get("type")), 0) + (
            int(q.item()) if hasattr(q, "item") else int(q))
    return out


@macros.tick("_pillar", shrink="budget")
def _pillar_tick(agent, pl: dict[str, Any], mk_act):
    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail("pillar_up: a screen is open; close it first.", "pillar_gui_flush")
        return None
    if pos is None:
        return mk_act()
    pl["used"] += 1

    if pl.get("inv0") is None:
        pl["inv0"] = _block_counts(agent)

    def _finish(why: str) -> None:
        agent.cursor_stats["pillar_up_blocks"] = (
            agent.cursor_stats.get("pillar_up_blocks", 0) + pl["placed"])
        # What left the inventory, not what was asked for: one life's pillar "of
        # cobblestone" was its last three obsidian, and the note said cobblestone.
        now = _block_counts(agent)
        gone = {k: v - now.get(k, 0) for k, v in pl["inv0"].items() if v - now.get(k, 0) > 0}
        other = {k: v for k, v in gone.items() if k != pl["item"]}
        wrong = ""
        if pl["placed"] and other and not gone.get(pl["item"]):
            what = ", ".join(f"{v} {k}" for k, v in sorted(other.items()))
            wrong = (f" NOT {pl['item']}: the inventory lost {what} -- that is what the "
                     f"pillar is made of ({pl['item']} was not the selected item).")
            agent.cursor_stats["pillar_wrong_item"] = (
                agent.cursor_stats.get("pillar_wrong_item", 0) + 1)
        agent.memory.add_note(
            f"pillar_up: {pl['placed']} of {pl['target']} {pl['item']} placed, now at y "
            f"{pos['y']:.1f}. {why}{wrong}")

    if pl["used"] > pl["budget"]:
        _finish("Budget spent.")
        return None
    if pl["phase"] == "look":
        dp = 90.0 - float(pos["pitch"])
        if dp > 2.0:
            return mk_act(camera=[min(30.0, dp), 0.0])
        pl["phase"], pl["t"], pl["y_jump"] = "jump", 0, float(pos["y"])
    t = pl["t"]
    pl["t"] += 1
    if t < 10:
        return mk_act(jump=1, use=1 if t >= 3 else 0)
    if t < 16:
        return mk_act()
    if float(pos["y"]) >= pl["y_jump"] + 0.9:
        pl["placed"] += 1
        pl["tries"] = 0
    else:
        pl["tries"] += 1
    if pl["placed"] >= pl["target"]:
        _finish("Done.")
        return None
    if pl["tries"] >= 2:
        _finish("The block did not place twice in a row -- no room above, or the item "
                "ran out / is not in the hotbar.")
        return None
    pl["t"], pl["y_jump"] = 0, float(pos["y"])
    return mk_act()


# -- multi-block builds -----------------------------------------------------------

#: What earlier builds placed, by build key (label + the full cell list): a plan is
#: capped at 400 ticks, so a wall or a portal frame is usually two or three calls, and
#: the second call must skip what the first placed (a re-placement is refused by the
#: game and three refusals in a row abort the build). Cleared when the world resets.
LAST_BUILDS: dict[str, dict[str, Any]] = {}


def build_key(label: str, cells: list) -> str:
    return label + ":" + ",".join(f"{x},{y},{z}" for x, y, z in sorted(tuple(c[:3]) for c in cells))


def remembered(label: str, cells: list) -> set:
    """Cells of this exact build that an earlier call already placed."""
    rec = LAST_BUILDS.get(build_key(label, cells))
    return {tuple(c) for c in rec["placed"]} if rec else set()


def _build_marker(targets: list[tuple[int, int, int, str]], item: str, spots: list | None,
                  label: str, sneak: bool = False, floor_y: float | None = None,
                  solid: list | None = None, key: str | None = None) -> dict[str, Any]:
    distinct = len({tuple(sp) for sp in (spots or [])})
    budget = len(targets) * PLACE_COST + distinct * 60
    return macros.marker("_build", {
        "targets": [[x, y, z, f] for x, y, z, f in targets], "spots": spots, "i": 0,
        "item": item, "label": label, "budget": budget, "used": 0, "placed": 0,
        "failed": 0, "consec": 0, "sub": None, "walk": None, "sneak": bool(sneak),
        "skipped": [], "ground_y": floor_y, "key": key,
        "solid": [list(c) for c in (solid or [])]}, budget)


def _line_targets(pos: dict[str, float], length: int, height: int, dist: int,
                  along: str) -> list[tuple[int, int, int, str]]:
    """Blocks of a wall `length` wide, `height` high, `dist` blocks ahead, centred on
    the avatar's facing (snapped to an axis). `along="ahead"` runs the wall AWAY from
    the avatar instead (a row from 1 block ahead)."""
    bx, by, bz = block_of(pos)
    dx, dz = axis_facing(pos["yaw"])
    px, pz = dz, -dx                        # perpendicular (to the right)
    out = []
    if along == "ahead":
        # Far to near within each 3-block segment, far segment first: a ground cell is
        # only reachable while the cells between it and the avatar are still empty
        # (the ray to a nearer cell never crosses a farther one), and the avatar
        # walks forward to a segment's spot over ground not yet built on.
        segs = list(range(0, length, 3))
        for s0 in reversed(segs):
            for j in reversed(range(s0, min(length, s0 + 3))):
                cx, cz = bx + dx * (1 + j), bz + dz * (1 + j)
                for h in range(height):
                    out.append((cx, by + h, cz, "below"))
    else:
        # Row by row, each row from the centre column outward: a block beside an
        # already-placed neighbour can be clicked on that neighbour's SIDE face,
        # which a shallow view of the row's top faces cannot be trusted for (see
        # `_build_tick`: the eye barely above a plane makes the aim marginal).
        start = -((length - 1) // 2)
        ks = sorted(range(start, start + length), key=lambda k: (abs(k), k))
        for h in range(height):
            for k in ks:
                cx, cz = bx + dx * dist + px * k, bz + dz * dist + pz * k
                out.append((cx, by + h, cz, "below"))
    return out


def build_wall(cur, info: dict, item: str = "cobblestone", length: int = 5,
               height: int = 2, dist: int = 2) -> tuple[list[dict[str, Any]], str]:
    """A wall `length` wide and `height` high, `dist` blocks ahead, across your facing."""
    return _build_lines(cur, info, item, length, height, dist, "across", "build_wall")


def build_row(cur, info: dict, item: str = "cobblestone", length: int = 5
              ) -> tuple[list[dict[str, Any]], str]:
    """A row of blocks on the ground running AWAY from you, from one block ahead."""
    return _build_lines(cur, info, item, length, 1, 1, "ahead", "build_row")


def build_column(cur, info: dict, item: str = "cobblestone", height: int = 3,
                 dist: int = 2) -> tuple[list[dict[str, Any]], str]:
    """A column `height` high, `dist` blocks ahead (a pillar you do not stand on)."""
    return _build_lines(cur, info, item, 1, height, dist, "across", "build_column")


def _build_lines(cur, info, item, length, height, dist, along, label):
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], f"{label}: no position yet."
    try:
        length, height, dist = int(length), int(height), int(dist)
    except (TypeError, ValueError):
        return [], f"{label}: length/height/dist must be integers."
    length, height = max(1, min(32, length)), max(1, min(6, height))
    dist = max(1, min(3, dist))
    if _is_nonplaceable(item):
        return [], f"{label}: {item} is not a block."
    have = sum(q for _, q in gui.find_slots(info, item))
    need = length * height
    if have < 1:
        return [], f"{label}: you carry no {item}."
    if have < need:
        return [], (f"{label}: {need} {item} needed for {length}x{height}, you carry "
                    f"{have} -- build a smaller piece.")
    bx, by, bz = block_of(pos)
    # A second call from the pillar top (or after a step-cap truncation) must plan the
    # SAME cells as the first: the ground is the remembered one, not the pillar top.
    prior = next((rec for k, rec in LAST_BUILDS.items() if k.startswith(label + ":")
                  and rec.get("ground_y") is not None
                  and math.dist((rec["spot"][0], rec["spot"][1]), (bx + 0.5, bz + 0.5)) < 1.0
                  and rec.get("params") == (length, height, dist, along, axis_facing(pos["yaw"]))),
                 None)
    if prior is not None:
        gpos = dict(pos)
        gpos["y"] = float(prior["ground_y"])
        by = int(prior["ground_y"])
    else:
        gpos = pos
    targets = _line_targets(gpos, length, height, dist, along)
    key = build_key(label, targets)
    done = remembered(label, targets)
    LAST_BUILDS.setdefault(key, {"placed": []}).update(
        {"ground_y": by, "spot": [bx + 0.5, bz + 0.5],
         "params": (length, height, dist, along, axis_facing(pos["yaw"]))})
    # Standing spots: for a wall across the facing, one spot per 7 columns along the
    # line; for a row running ahead, the block behind each target (walk backwards).
    dx, dz = axis_facing(pos["yaw"])
    px, pz = dz, -dx
    spots: list[list[float]] = []
    if along == "ahead":
        # Matches `_line_targets`' order: each segment's cells are placed from the
        # spot at the segment's start (0, 3, 6 ... blocks ahead).
        segs = list(range(0, length, 3))
        for s0 in reversed(segs):
            for _j in reversed(range(s0, min(length, s0 + 3))):
                spots.append([bx + dx * s0 + 0.5, bz + dz * s0 + 0.5])
    else:
        start = -((length - 1) // 2)
        ks = sorted(range(start, start + length), key=lambda k: (abs(k), k))
        spot_of_k = {}
        for k in range(start, start + length):
            seg = (k - start) // 7
            centre_k = start + seg * 7 + 3
            spot_of_k[k] = [bx + px * centre_k + 0.5, bz + pz * centre_k + 0.5]
        for _h in range(height):
            for k in ks:
                spots.append(spot_of_k[k])
    per_target = list(spots)            # one per target, in target order
    acts, err = _prep_item(cur, info, item, label)
    if err:
        return [], err
    pairs = [(t, sp) for t, sp in zip(targets, per_target) if tuple(t[:3]) not in done]
    if not pairs:
        return [], (f"{label}: all {len(targets)} cells of this build are already placed "
                    f"(from where you stand, with these parameters).")
    solid0 = [list(c) for c in done]
    if along == "across" and height > 1:
        # Row h is built with the avatar standing h blocks up: a support's top face
        # is hidden once it rises above the eye, and even 0.62 below the eye (row 1
        # from the ground) the view grazes it -- a 1.5-degree aim error moved the
        # click onto the block's front and the last block of every row landed one
        # cell forward (a staged scene). With the eye 1.62 above every row's
        # plane the ray meets the face squarely. Row 0 from the ground; then one
        # pillar block of `item` per row, from the same spot. The pillar stays
        # (walking off a 3-block drop costs nothing). A call from the pillar top --
        # a resumed build -- pillars only what is still missing.
        cur_lift = max(0, int(round(pos["y"] - by)))
        lift_total = max(0, (height - 1) - cur_lift)
        if have < len(pairs) + lift_total:
            return [], (f"{label}: {len(pairs) + lift_total} {item} needed ({len(pairs)} "
                        f"for the wall, {lift_total} to stand on while building the upper "
                        f"rows); you carry {have}.")
        spot = [bx + 0.5, bz + 0.5]
        solid = list(solid0)
        lifted = cur_lift
        for h in range(height):
            row = [(t, sp) for t, sp in pairs if t[1] == by + h]
            if not row:
                continue
            if h > lifted:
                n = h - lifted
                acts.append(macros.marker("_pillar", {
                    "item": item, "target": n, "placed": 0, "phase": "look", "t": 0,
                    "tries": 0, "y_jump": None, "budget": n * 24 + 30, "used": 0},
                    n * 24 + 30))
                lifted = h
            spots_h = [sp for _, sp in row] if h == 0 else [spot] * len(row)
            acts.append(_build_marker([t for t, _ in row], item, spots_h, label,
                                      floor_y=by, solid=list(solid), key=key))
            solid += [list(t[:3]) for t, _ in row]
    else:
        acts.append(_build_marker([t for t, _ in pairs], item, [sp for _, sp in pairs],
                                  label, floor_y=by, solid=solid0, key=key))
    first, last = targets[0], targets[-1]
    return acts, (f"{label}: {len(pairs)} {item} to place"
                  + (f" ({len(done)} already there)" if done else "")
                  + f" from {first[:3]} to {last[:3]} ({length} wide x {height} high), "
                  f"facing {'x' if dx else 'z'}{'+' if (dx + dz) > 0 else '-'}. A plan holds "
                  f"~400 ticks: if the note says the budget ran out, call it again with the "
                  f"same arguments from the same spot -- placed cells are skipped.")


def bridge_forward(cur, info: dict, n: int = 5, item: str = "cobblestone"
                   ) -> tuple[list[dict[str, Any]], str]:
    """Extend the floor ahead one block at a time (over water, lava, a drop), stepping
    onto each block placed. Sneak is held while walking so you cannot fall off."""
    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "bridge_forward: no position yet."
    n = max(1, min(32, int(n)))
    have = sum(q for _, q in gui.find_slots(info, item))
    if have < n:
        return [], f"bridge_forward: {n} {item} needed, you carry {have}."
    bx, by, bz = block_of(pos)
    dx, dz = axis_facing(pos["yaw"])
    back = {(0, 1): "north", (0, -1): "south", (1, 0): "west", (-1, 0): "east"}[(dx, dz)]
    # The side face of the block you stand on is hidden behind its own top face from
    # anywhere ON the block: the ray reaches the face plane exactly where it crosses
    # foot level (a staged scene: four blocks placed, all one level down, the
    # avatar walking off them into the trench). The face is reachable only with the
    # eye PAST the edge. Measured: sneaking does NOT stop
    # the walk at an edge in this engine, but the hitbox lets the position overhang
    # by ~0.25 before falling, and a sneak-walk moves ~0.055 blocks a tick -- so the
    # standing spot is the edge + 0.2 (centre + 0.7 along the heading), reached one
    # tick at a time, and the aim turns around to look back down at the face: from
    # there the face spans pitch 82-85 degrees, so the aim tolerance is tightened.
    targets, spots = [], []
    for i in range(1, n + 1):
        targets.append((bx + dx * i, by - 1, bz + dz * i, back))
        spots.append([bx + dx * (i - 1) + 0.5 + dx * BRIDGE_OVERHANG,
                      bz + dz * (i - 1) + 0.5 + dz * BRIDGE_OVERHANG])
    acts, err = _prep_item(cur, info, item, "bridge_forward")
    if err:
        return [], err
    mk = _build_marker(targets, item, spots, "bridge_forward", sneak=True)
    mk["_build"]["floor_y"] = float(by)
    acts.append(mk)
    return acts, (f"bridge_forward: {n} {item} ahead along "
                  f"{'x' if dx else 'z'}{'+' if (dx + dz) > 0 else '-'}")


def _walk_step(agent, wk: dict[str, Any], mk_act, sneak: bool):
    """One tick toward wk['spot'] (x, z); returns (status, action)."""
    pos = agent._cur_pos
    sx, sz = wk["spot"]
    dx, dz = sx - pos["x"], sz - pos["z"]
    dist = math.hypot(dx, dz)
    if dist <= (BRIDGE_WALK_TOL if sneak else 0.25):
        return "done", None
    wk["t"] += 1
    if wk["t"] > 80:
        return "failed", None
    last = wk.get("last")
    if last is not None and math.hypot(pos["x"] - last[0], pos["z"] - last[1]) < 0.01:
        wk["stuck"] = wk.get("stuck", 0) + 1
        if wk["stuck"] >= 8:
            return "failed", None
    else:
        wk["stuck"] = 0
    wk["last"] = (pos["x"], pos["z"])
    yaw_t = math.degrees(math.atan2(-dx, dz))
    dy = norm_yaw_delta(yaw_t, pos["yaw"])
    if abs(dy) > 15.0:
        return "run", mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
    slow = dist < 0.8
    if sneak and dist < 0.2 and abs(dy) > 3.0:
        # Straighten first: a crooked last step overhangs sideways.
        return "run", mk_act(camera=[0.0, max(-10.0, min(10.0, dy))])
    return "run", mk_act(forward=1, sneak=1 if (sneak or slow) else 0,
                         camera=[0.0, max(-6.0, min(6.0, dy))])


@macros.tick("_build", shrink="budget", moving=True)
def _build_tick(agent, bd: dict[str, Any], mk_act):
    if agent._gui_open:
        agent._flush_tail(f"{bd['label']}: a screen is open; close it first.",
                          "build_gui_flush")
        return None
    pos = agent._cur_pos
    if pos is None:
        return mk_act()
    bd["used"] += 1
    n = len(bd["targets"])

    def _finish(why: str) -> None:
        agent.cursor_stats["build_placed"] = (
            agent.cursor_stats.get("build_placed", 0) + bd["placed"])
        rest = n - bd["i"]
        agent.memory.add_note(
            f"{bd['label']}: placed {bd['placed']} of {n} {bd['item']}"
            + (f", {bd['failed']} spot(s) refused" if bd["failed"] else "")
            + (f", {rest} not attempted" if rest else "") + f". {why}"
            + (f" Not placed: {', '.join(str(tuple(t)) for t in bd['skipped'][:6])}."
               if bd["skipped"] else ""))

    if bd["i"] >= n:
        _finish("Done.")
        return None
    if bd.get("floor_y") is not None and pos["y"] < bd["floor_y"] - 0.5:
        _finish("STOPPED: you dropped below the bridge level -- a block went to the "
                "wrong cell or you walked off the edge. Climb back (pillar_up) and "
                "start again from the edge, sneaking.")
        return None
    if bd["used"] > bd["budget"]:
        _finish("Budget spent -- call it again for the rest (blocks already there are "
                "skipped as 'refused').")
        return None
    x, y, z, face = bd["targets"][bd["i"]]
    target = (int(x), int(y), int(z))
    # Walk to the standing spot when the target is out of reach from here.
    if bd["sub"] is None:
        _, _, dist = angles_to(pos, aim_point(target, face))
        spot = bd["spots"][bd["i"]] if bd["spots"] else None
        need_walk = spot is not None and (
            dist > REACH - 0.3 or overlaps_player(target, pos)
            or (bd["sneak"] and math.hypot(pos["x"] - spot[0], pos["z"] - spot[1]) > 0.35))
        if need_walk and bd["walk"] is None:
            bd["walk"] = {"spot": spot, "t": 0}
        if bd["walk"] is not None:
            status, action = _walk_step(agent, bd["walk"], mk_act, bd["sneak"])
            if status == "run":
                return action
            bd["walk"] = None
            if status == "failed":
                bd["failed"] += 1
                bd["consec"] += 1
                bd["skipped"].append(target)
                bd["i"] += 1
                if bd["consec"] >= 3:
                    _finish("STOPPED: three targets in a row could not be reached "
                            "(blocked walk). Clear the way or build from another side.")
                    return None
                return mk_act()
        if not bd["sneak"]:
            # Only a face whose plane the eye can see is worth a click: a hidden one
            # lands the block in front of the support (use_item still moves, so the
            # verdict would be a false "placed"). Candidates: the asked face, then
            # the others whose support is a known solid (ground or already placed).
            solid = {tuple(c) for c in bd["solid"]}
            gy = bd.get("ground_y")
            # The eye less than a block above a top face sees it at a grazing angle:
            # a 1.5-degree aim error over 2-3 blocks moves the ray past the face's
            # edge onto the block's FRONT (the block lands one cell toward you; stage
            # s2) or over its back. A vertical side face has a full
            # block of margin, so beside a placed neighbour it is clicked instead.
            shallow = (pos["y"] + EYE) - float(target[1]) < 1.0
            sides = ["west", "east", "north", "south"]
            order = ([face] + [f for f in sides + ["below"] if f != face]
                     if not (shallow and face == "below")
                     else sides + ["below"])
            usable = []
            for f in order:
                ox, oy, oz = FACE_OFFSET[f]
                sup = (target[0] + ox, target[1] + oy, target[2] + oz)
                known = sup in solid or (gy is not None and sup[1] < gy)
                if known and face_visible(pos, target, f, solid, gy):
                    usable.append(f)
            if not usable:
                bd["failed"] += 1
                bd["consec"] += 1
                bd["skipped"].append(target)
                bd["hidden"] = bd.get("hidden", 0) + 1
                bd["i"] += 1
                if bd["consec"] >= 3:
                    _finish("STOPPED: no visible face to build these on from here -- "
                            "their supports' top faces are above your eye. Stand higher "
                            "(pillar_up) or further back, then call it again.")
                    return None
                return mk_act()
            face = usable[0]
        bd["sub"] = new_use_state(target, bd["item"], face, "place", 1, bd["label"],
                                  tol=BRIDGE_AIM_TOL if bd["sneak"] else AIM_TOL,
                                  faces=[face] if bd["sneak"] else list(usable))
    status, action = use_step(agent, bd["sub"], mk_act)
    if status == "run":
        return action
    if status == "done":
        bd["placed"] += 1
        bd["consec"] = 0
        bd["solid"].append(list(target))
        if bd.get("key"):
            LAST_BUILDS.setdefault(bd["key"], {"placed": []})["placed"].append(list(target))
    else:
        bd["failed"] += 1
        bd["consec"] += 1
        bd["skipped"].append(target)
    bd["sub"] = None
    bd["i"] += 1
    if bd["consec"] >= 3:
        _finish("STOPPED: three placements in a row were refused -- the item is gone "
                "from the hotbar, the spots are already filled, or nothing solid is "
                "there to build on. Look at the frame before calling it again.")
        return None
    return mk_act()


# -- look around ---------------------------------------------------------------------

def scan_around(steps: int = 8, pitch: float = 0.0) -> list[dict[str, Any]]:
    steps = max(4, min(12, int(steps)))
    return [macros.marker("_scan", {"steps": steps, "k": 0, "t": 0, "yaw0": None,
                                    "pitch": max(-60.0, min(60.0, float(pitch))),
                                    "frames": [], "phase": "turn"}, steps * 14 + 20)]


@macros.tick("_scan")
def _scan_tick(agent, sc: dict[str, Any], mk_act):

    pos = agent._cur_pos
    if agent._gui_open:
        agent._flush_tail("scan_around: a screen is open; close it first.", "scan_gui_flush")
        return None
    if pos is None:
        return mk_act()
    if sc["yaw0"] is None:
        sc["yaw0"] = float(pos["yaw"])
    steps = sc["steps"]
    if sc["k"] >= steps:
        # back to the starting heading, then the sheet
        dy = norm_yaw_delta(sc["yaw0"], pos["yaw"])
        if abs(dy) > 3.0 and sc["t"] < 12:
            sc["t"] += 1
            return mk_act(camera=[0.0, max(-30.0, min(30.0, dy))])
        sheet = _contact_sheet(agent, sc["frames"])
        headings = ", ".join(f"{h:.0f}" for _, h in sc["frames"])
        agent.cursor_stats["scans"] = agent.cursor_stats.get("scans", 0) + 1
        agent.memory.add_note(
            f"scan_around: {len(sc['frames'])} views at yaws {headings} (pitch "
            f"{sc['pitch']:.0f})" + (f" tiled into {sheet} (open it with view_image); "
                                    f"each tile is labelled with its yaw -- look_abs(yaw=...) "
                                    f"faces it." if sheet else ".")
            + " Back at the starting heading.")
        return None
    target_yaw = sc["yaw0"] + 360.0 * sc["k"] / steps
    if sc["phase"] == "turn":
        dy = norm_yaw_delta(target_yaw, pos["yaw"])
        dp = sc["pitch"] - pos["pitch"]
        sc["t"] += 1
        if (abs(dy) <= 2.0 and abs(dp) <= 2.0) or sc["t"] > 12:
            sc["phase"], sc["t"] = "settle", 0
            return mk_act()
        return mk_act(camera=[max(-30.0, min(30.0, dp)), max(-30.0, min(30.0, dy))])
    # settle: one tick for the frame to catch up, then save
    if sc["t"] < 1:
        sc["t"] += 1
        return mk_act()
    data = agent._encode_pov(agent._last_pov, agent.step)
    rel = agent.memory.save_frame(agent.step, data, suffix=f"_scan{sc['k']}") if data else None
    if rel:
        sc["frames"].append((rel, (pos["yaw"] % 360.0)))
    sc["k"] += 1
    sc["phase"], sc["t"] = "turn", 0
    return mk_act()


def _contact_sheet(agent, frames: list[tuple[str, float]]) -> str | None:
    """Tile the scan frames (half size, 4 per row) with yaw labels; returns the saved
    path (relative to the memory root) or None."""
    from PIL import Image, ImageDraw

    if not frames:
        return None
    try:
        tiles = []
        for rel, yaw in frames:
            img = Image.open(agent.memory.root / rel).convert("RGB").resize((320, 180))
            ImageDraw.Draw(img).text((6, 4), f"yaw {yaw:.0f}", fill=(255, 255, 0))
            tiles.append(img)
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (320 * cols, 180 * rows), (0, 0, 0))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * 320, (i // cols) * 180))
        buf = io.BytesIO()
        sheet.save(buf, format="PNG")
        return agent.memory.save_frame(agent.step, buf.getvalue(), suffix="_scansheet")
    except Exception as e:      # a sheet failure must never end the plan
        agent.memory.add_note(f"scan_around: could not tile the frames ({e}); the "
                              f"individual frames are saved.")
        return None


# -- bed --------------------------------------------------------------------------

def sleep_in_bed(cur, info: dict, x: float = 0.0, y: float = 0.0, z: float = 0.0
                 ) -> tuple[list[dict[str, Any]], str]:
    """Right-click the bed at (x, y, z) and wait for the night to pass."""
    acts, note = use_at(cur, info, x, y, z, item=None, face="above", hold=2)
    if not acts:
        return acts, note
    acts.append(macros.marker("_sleep", {"t": 0, "budget": 160}, 160))
    return acts, f"sleeping in the bed at ({x}, {y}, {z})"


@macros.tick("_sleep", shrink="budget")
def _sleep_tick(agent, sl: dict[str, Any], mk_act):
    sl["t"] += 1
    if sl["t"] < 6:
        return mk_act()
    if not agent._gui_open:
        agent.memory.add_note(
            "sleep_in_bed: the bed screen is closed -- either the night has passed "
            "(you were asleep) or the bed could not be used (only at night, and not "
            "with monsters nearby). Check the sky / the frame.")
        return None
    if sl["t"] >= sl["budget"]:
        agent.memory.add_note("sleep_in_bed: still in bed after the budget; the night "
                              "is passing -- call it again, or close_inventory to leave.")
        return None
    return mk_act()


# -- registration ---------------------------------------------------------------------

def register_all(register, Procedure) -> None:
    register(Procedure(
        "place_at",
        "Put `item` INTO the block cell (x, y, z) by clicking a face of the block it "
        "rests on (default: the block BELOW it, i.e. build on the ground / on the block "
        "under it; `face=\"north\"` etc. attaches to that neighbour, e.g. a torch or an "
        "item frame on a wall). Aims from the live position, verifies on use_item, "
        "tries the nearest other face on a refusal, and says what happened.",
        place_at, needs_cursor=True, needs_info=True,
        preconditions="Within 4 blocks, not the cell you stand in, no screen open. "
                      "Coordinates are block coordinates (floor of a position).",
        params={"x": "block x", "y": "block y", "z": "block z", "item": "block to place",
                "face": "below|above|north|south|west|east (the neighbour to click)"}))
    register(Procedure(
        "use_at",
        "Right-click a face of the block at (x, y, z) with `item` selected: pour a water "
        "bucket (item=water_bucket, the ground block), light with flint_and_steel, till "
        "with a hoe, plant seeds on farmland, shear a pumpkin, open a door / bed, or "
        "`item` omitted = use the block with what you hold (a chest, a door). A crafting "
        "table or furnace placed earlier opens this way. Verified on use_item / the "
        "inventory / a screen opening.",
        use_at, needs_cursor=True, needs_info=True,
        preconditions="Within 4 blocks, no screen open. `face` = which side of the "
                      "block to click (below = its top surface as seen from above).",
        params={"x": "block x", "y": "block y", "z": "block z",
                "item": "item to hold (optional)", "face": "below (default) | above | "
                "north | south | west | east", "hold": "ticks to hold use (default 1)"}))
    register(Procedure(
        "use_held",
        "Hold `use` with an item selected: draw a bow (hold>=25 then it releases), "
        "drink a potion (32), look through a spyglass, raise a shield (hold as long as "
        "you want to block). Verified on use_item / the inventory.",
        use_held, needs_cursor=True, needs_info=True,
        preconditions="Aim first (look_at) for a bow. No screen open.",
        params={"item": "item to select (optional: keep what is held)",
                "hold": "ticks to hold (default 32)"}))
    register(Procedure(
        "fill_bucket",
        "Fill an EMPTY bucket at water you can see: holds the bucket and sweeps the "
        "crosshair over the ground ahead (pitch 18-60, yaw +-40), tapping use at each aim "
        "until a filled bucket appears in the inventory (verified on the inventory; it "
        "names water_bucket / lava_bucket / milk_bucket, whatever the sweep met). No "
        "coordinates or faces to guess, unlike use_at(bucket).",
        fill_bucket, needs_cursor=True, needs_info=True,
        preconditions="An empty `bucket` carried; still water (a source block, not a "
                      "stream) 1-3 blocks ahead and below the eye, within 4 blocks; no "
                      "screen open.",
        params={"ticks": "sweep budget (default 260: 25 aims of ~9 ticks)"}))
    register(Procedure(
        "fetch_water",
        "Get to water you can see and fill the bucket: looks around for the blue of still "
        "water (12 headings, if none is in view), walks toward it correcting the heading on "
        "every frame, breaks the leaves or dirt that stop the walk (a trunk is side-stepped), "
        "stops at the shore and runs fill_bucket there. The one call for a pond behind trees "
        "or across a clearing; go_to only walks to a coordinate and stops at the first "
        "obstacle.",
        fetch_water, needs_cursor=True, needs_info=True,
        preconditions="An empty `bucket` carried; still water (a pond, river or lake, not "
                      "a stream's flow) visible from here or within a turn of the head; no "
                      "screen open.",
        params={"n": "tick budget for the search and walk (default 600; the plan's step cap "
                     "shrinks it -- call it again to continue); the sweep at the shore adds "
                     "up to 260"}))
    register(Procedure(
        "throw",
        "Throw a snowball / egg / ender pearl / eye of ender: taps use `n` times with the "
        "item selected; verified on the count going down.",
        throw, needs_cursor=True, needs_info=True,
        preconditions="Aim first; no screen open.",
        params={"item": "throwable item name", "n": "how many (default 1)"}))
    register(Procedure(
        "eat",
        "Eat food (the best carried when unnamed); holds use ~40 ticks. Only works while "
        "the food bar is below 20.",
        eat, needs_cursor=True, needs_info=True,
        params={"item": "food item (optional)"}))
    register(Procedure(
        "watch",
        "Do nothing for up to `n` ticks and stop the moment `until` holds, read from the "
        "game's own numbers: none (a plain wait), inventory (any count changes), gui (a "
        "screen opens), health, damage, y_below:<v>, y_above:<v>, moved:<blocks>. The "
        "observe step between acting and deciding; ends with a [NOTE] saying what "
        "happened.",
        watch, params={"until": "condition (default none)", "n": "ticks, max 400 (default 60)"}))
    register(Procedure(
        "pillar_up",
        "Jump and place `n` blocks under your feet (each verified on the measured y): a "
        "tower to stand on, a lookout, an escape from a mob. Uses cobblestone/dirt/planks "
        "from the hotbar when `item` is omitted.",
        pillar_up, needs_cursor=True, needs_info=True,
        preconditions="Clear air above you; a placeable block carried.",
        params={"n": "blocks (1-30)", "item": "block name (optional)"}))
    register(Procedure(
        "build_wall",
        "A wall `length` wide x `height` high, `dist` blocks AHEAD of you, running "
        "left-right across your facing (snapped to an axis), built from where you stand "
        "block by block with each placement verified; walks along the line for long "
        "walls. Reports placed / refused / not attempted, and resumes on a second call.",
        build_wall, needs_cursor=True, needs_info=True,
        preconditions="Flat ground ahead; carry length x height blocks plus height-1 to "
                      "stand on (each upper row is built from one block higher); face "
                      "the wall's middle. Max height 6.",
        params={"item": "block", "length": "blocks wide (1-32)", "height": "1-6",
                "dist": "blocks ahead (1-3, default 2)"}))
    register(Procedure(
        "build_row",
        "A row of blocks on the ground running AWAY from you, from the block ahead: "
        "the far cells first, from where you stand, walking forward for the farther "
        "segments before they are built (a path, a fence line, a carpet strip).",
        build_row, needs_cursor=True, needs_info=True,
        preconditions="Flat, walkable ground along the row; carry `length` blocks.",
        params={"item": "block", "length": "blocks (1-32)"}))
    register(Procedure(
        "build_column",
        "One column `height` high, `dist` blocks ahead of you (a pillar you look at, a "
        "snow golem body, a portal post).",
        build_column, needs_cursor=True, needs_info=True,
        params={"item": "block", "height": "1-6", "dist": "blocks ahead (default 2)"}))
    register(Procedure(
        "bridge_forward",
        "Extend the floor ahead `n` blocks over water / lava / a drop, stepping onto each "
        "placed block with sneak held (you cannot fall off). Faces snap to an axis.",
        bridge_forward, needs_cursor=True, needs_info=True,
        preconditions="Stand at the edge facing the gap; carry n blocks.",
        params={"n": "blocks (1-32)", "item": "block (default cobblestone)"}))
    register(Procedure(
        "scan_around",
        "Turn a full circle in `steps` headings, saving a frame at each, and attach ONE "
        "contact sheet of them (yaw-labelled tiles) to your next turn -- the look-around "
        "for finding anything (a village, water, lava, sand, a tree line, a mob). Ends "
        "facing where you started.",
        lambda steps=8, pitch=0.0: scan_around(steps, pitch),
        preconditions="No screen open. Stand somewhere with a view (a hilltop, a pillar).",
        params={"steps": "4-12 (default 8)", "pitch": "camera pitch for the sweep "
                "(default 0; -20 looks slightly up for mountains/sky)"}))
    register(Procedure(
        "sleep_in_bed",
        "Right-click the bed at (x, y, z) and wait the night out (the bed screen opens; "
        "it closes when morning comes).",
        sleep_in_bed, needs_cursor=True, needs_info=True,
        preconditions="Night time, within 3 blocks of the bed, no monsters near.",
        params={"x": "bed block x", "y": "bed block y", "z": "bed block z"}))
