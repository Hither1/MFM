"""Block geometry from the exact [STATE] pose, and the one place / use engine.

What is left of the harness's world macros (2026-10-24: no arm has a built-in procedure,
procedures.py): the facing and block arithmetic the chassis reads a position with, the
aim at a world block face (trigonometry from the live pose, every tick), and the
aim -> click -> verify machine `use_step`, verified on the `use_item` statistic and the
inventory, never on the frame. The runner's own reflexes (`harness_reflexes`, off in
every arm) cap a bunker with it; nothing here is a skill the model is given.
"""
from __future__ import annotations

import math
from typing import Any



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


#: Face names and the unit offset from the TARGET to its SUPPORT block.
FACE_OFFSET = {"below": (0, -1, 0), "above": (0, 1, 0), "north": (0, 0, -1),
               "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0)}


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


def norm_yaw_delta(target: float, cur: float) -> float:
    return (target - cur + 180.0) % 360.0 - 180.0


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
