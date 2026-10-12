"""One-call GUI macros: craft, place-and-open, furnace load/take, mine-until.

Why these exist. Across the landed dragon runs, 57-72% of every plan's entries were
cursor micro-work -- cursor_to_slot, gui_click, cursor_to_cell, gui_right_click, repeated
per ingredient and per cell (one run 447 of 738 entries; another 660 of 921). The model
was doing by hand, turn after turn, what is arithmetic over the real inventory: which
slot holds the ingredient, which cell wants it, where the output goes. Every one of those
hand-written sequences was also unverified until the next turn read [INV].

What changed to make a macro possible. The 2026-08 open-loop `craft` moved nothing
because the cursor's scale and origin were guesses. The measured cursor fixed that: a
`_servo` marker lands on a slot against the pointer found in each frame, and a `_click`
marker is held against the screen it is about to touch. The macros here emit exactly
those entries -- the same closed loop the models converged on -- compiled from
`info['inventory']` at plan time, and they end with a check against the statistic that
cannot lie (`craft_item`, `use_item`, the inventory count) so a failure is reported
in the same plan instead of a turn later.

Every action still goes through `sim.step` and every milestone still fires only when
MineRL's own statistic moves; this is a skill library over the primitive action space,
not a shortcut around the benchmark.
"""
from __future__ import annotations

import math
from typing import Any

from mcu_worldmodel import gui, macros
from mcu_worldmodel.milestones import _stat, slot_is_empty

#: Recipe keys whose crafted item has a different name in the statistics.
PRODUCT = gui.PRODUCT

#: Items that do not stack, and belong in the hotbar when they are made.
_TOOL_WORDS = ("pickaxe", "sword", "axe", "shovel", "hoe", "flint_and_steel", "bucket",
               "shield", "bow", "helmet", "chestplate", "leggings", "boots",
               "crafting_table", "furnace", "boat", "shears", "fishing_rod", "bed",
               "clock", "compass", "enchanting_table", "stonecutter", "brewing_stand")
#: What one unit of a fuel smelts, in items (Minecraft 1.16 burn times / 200 ticks).
FUEL_PER_UNIT = {"coal": 8.0, "charcoal": 8.0, "@planks": 1.5, "@logs": 1.5,
                 "stick": 0.5, "crafting_table": 1.5}
FUEL_AUTO = ("coal", "charcoal", "@planks", "@logs", "stick")
#: Aim for the block in front at foot level: from the eye (1.62 up) a 55-degree ray
#: reaches ground level 1.1 blocks ahead -- the top face of the block the avatar is
#: about to put a table on. After the placement the same ray meets the placed block.
PLACE_PITCH = 55.0


# -- inventory arithmetic ---------------------------------------------------

def _entry(info: dict, slot: int) -> dict | None:
    inv = info.get("inventory") or {}
    e = inv.get(slot)
    if e is None:
        e = inv.get(str(slot))
    return e if isinstance(e, dict) else None


def _slot_item(info: dict, slot: int) -> tuple[str | None, int]:
    e = _entry(info, slot)
    if e is None or slot_is_empty(e):
        return None, 0
    q = e.get("quantity", 0)
    q = int(q.item()) if hasattr(q, "item") else int(q)
    return str(e.get("type")), q


def is_tool(item: str) -> bool:
    return any(w in item for w in _TOOL_WORDS)


def deposit_slot(info: dict, item: str, count: int, slot: Any = None
                 ) -> tuple[int | None, str]:
    """Where a stack of `count` `item` taken out of a grid should be banked.

    An explicit `slot` must be empty or hold the same item with room. Otherwise a
    stackable item joins an existing stack, and a tool goes to an empty HOTBAR slot
    first -- a pickaxe banked in row two cannot be selected with hotbar.N and cost
    runs another GUI trip to move it.
    """
    if slot is not None:
        try:
            s = int(slot)
        except (TypeError, ValueError):
            return None, f"bad slot {slot!r}"
        if not 0 <= s <= 35:
            return None, f"slot must be 0-35, not {s}"
        t, q = _slot_item(info, s)
        if t is None or (t == item and q + count <= 64):
            return s, ""
        return None, f"slot {s} holds {t} x{q}; pick an empty slot or one holding {item}"
    if not is_tool(item):
        for s in range(36):
            t, q = _slot_item(info, s)
            if t == item and q + count <= 64:
                return s, ""
    order = (list(range(9)) + list(range(9, 36)) if is_tool(item)
             else list(range(9, 36)) + list(range(9)))
    for s in order:
        if _slot_item(info, s)[0] is None:
            return s, ""
    return None, "every inventory slot is full -- discard_stack something first"


def _screen_is_open(cur, info: dict) -> bool:
    return bool(getattr(cur, "is_open", False)) or bool(info.get("isGuiOpen", False))


#: What a macro's cursor move is charged against the plan's step cap. The servo keeps
#: its 16-tick give-up budget at run time, but real moves land in 3-6 ticks and a
#: furnace recipe is twelve of them: charged at 16 each, two crafts overran the
#: 400-tick cap and the second was truncated mid-grid (a staged scene).
SERVO_CHARGE = 10


def _charge(acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for a in acts:
        if "_servo" in a:
            a["_cost"] = min(int(a.get("_cost", SERVO_CHARGE)), SERVO_CHARGE)
    return acts


# -- craft ------------------------------------------------------------------

def recipe_name(item: Any) -> str:
    """The recipe key a model's spelling means: `minecraft:stick`, `sticks`,
    `oak_planks`, `eye_of_ender` (the milestone's name for `ender_eye`). One run's first
    act turn lost its plan to "no recipe for 'sticks'"."""
    name = str(item).strip().lower()
    if name.startswith("minecraft:"):
        name = name[len("minecraft:"):]
    if name in gui.RECIPES:
        return name
    if name.endswith("_planks"):
        return "planks"
    if name in ("eye_of_ender", "ender_eyes"):
        return "ender_eye"
    if name.endswith("s") and name[:-1] in gui.RECIPES:
        return name[:-1]
    return name


def torch_recipe(item: str, info: dict) -> str:
    """`torch` with no coal but charcoal in hand is the charcoal recipe: the dark-tunnel
    line says charcoal works the same, and a refusal "need 1x coal, have 0" would be
    the runner contradicting itself (audit pass 9)."""
    if (item == "torch" and not gui.find_slots(info, "coal")
            and gui.find_slots(info, "charcoal")):
        return "charcoal_torch"
    return item


def craft(cur, info: dict, item: str = "crafting_table", count: int = 1,
          slot: Any = None) -> tuple[list[dict[str, Any]], str]:
    """The whole recipe as one entry: lift each ingredient stack, right-click one item
    into every cell it feeds, put the remainder back, take the output `count` times,
    bank it, verify against `craft_item`. The right screen must already be open."""
    from mcu_worldmodel import procedures as P

    item = torch_recipe(recipe_name(item), info)
    try:
        count = max(1, min(64, int(count)))
    except (TypeError, ValueError):
        return [], f"craft: bad count {count!r}"
    spec = gui.RECIPES.get(item)
    if spec is None:
        return [], (f"craft: no recipe for {item!r}. Known: "
                    f"{', '.join(sorted(gui.RECIPES))}.")
    grid, cells, out_n = spec
    product = PRODUCT.get(item, item)
    per: dict[str, int] = {}
    for ing in cells.values():
        per[ing] = per.get(ing, 0) + 1
    # Craft as many as the ingredients allow, up to `count`, rather than refusing the
    # whole call: one run asked for 3 planks crafts with 2 logs in hand
    # and got "need 3x logs, have 2" four times over -- 8 planks were a table and
    # sticks away the whole time.
    possible = count
    short = ""
    for ing, n1 in per.items():
        have = sum(q for _, q in gui.find_slots(info, ing))
        if have < n1:
            return [], (f"craft {item}: need {n1 * count}x {ing.lstrip('@')}, have {have}"
                        + (f" (for {count} crafts)" if count > 1 else ""))
        if have // n1 < possible:
            possible = have // n1
            short = f"only {possible} of the {count} asked: {have} {ing.lstrip('@')} in hand"
    count = possible
    need: dict[str, int] = {ing: n1 * count for ing, n1 in per.items()}
    if not _screen_is_open(cur, info):
        where = ("open_inventory first (a 2x2 recipe)" if grid == "2x2" else
                 'place_and_open(item="crafting_table") first, or use_at your placed '
                 'table (a 3x3 recipe)')
        return [], f"craft {item}: no screen is open -- {where}."
    target, why = deposit_slot(info, product, count * out_n, slot)
    if target is None:
        return [], f"craft {item}: nowhere to bank the output -- {why}"
    del target                       # quick-move picks the slot itself; see below

    # Spend each source stack down as cells consume it (two cells wanting the same
    # ingredient must not both plan to take it from a slot holding one).
    remaining: dict[str, list[list[int]]] = {
        ing: [[s, q] for s, q in gui.find_slots(info, ing)] for ing in need}
    src_qty: dict[int, int] = {}
    by_source: dict[int, list[int]] = {}
    for cell, ing in sorted(cells.items()):
        for _ in range(count):
            stacks = remaining[ing]
            while stacks and stacks[0][1] <= 0:
                stacks.pop(0)
            if not stacks:
                return [], f"craft {item}: ran out of {ing.lstrip('@')} filling the grid"
            s = stacks[0][0]
            src_qty.setdefault(s, stacks[0][1])
            stacks[0][1] -= 1
            by_source.setdefault(s, []).append(cell)

    kind = "inventory" if grid == "2x2" else "table"
    in_cells = gui.SURVIVAL_CRAFT_IN if grid == "2x2" else gui.TABLE_CRAFT_IN
    label = f"craft({item})"
    acts: list[dict[str, Any]] = [macros.marker("_screen_need", {
        "kind": kind, "label": label, "cells_clear": [list(in_cells[c]) for c in cells],
        "grid": grid, "base_event": "craft_item", "base_item": product}, 0)]
    for src, cell_list in by_source.items():
        a, err = P.cursor_to_slot(cur, src)
        if err:
            return [], f"craft {item}: {err}"
        acts += a + P.click("attack")                       # lift the stack
        for cell in cell_list:
            a, err = P.cursor_to_cell(cur, grid, cell)
            if err:
                return [], f"craft {item}: {err}"
            acts += a + P.click("use")                      # one item into the cell
        a, _ = P.cursor_to_slot(cur, src)
        if src_qty[src] - len(cell_list) > 0:
            acts += a + P.click("attack")                   # remainder back
        else:
            # A plain click on the (now empty) source slot even with nothing to put
            # back. Measured (a staged scene, 5 of 5 one-rod crafts): when
            # the LAST item of a stack goes into a cell by right-click and the very
            # next click is the shift-click on the output, craft_item moves (+2
            # blaze_powder) but the product lands in no slot and the GUI frame stops
            # updating (the cell keeps showing the rod for every later screen); with
            # any left-click in between the product lands in the hotbar.
            acts += a + P.click("attack", probe=True)
    a, _ = P.cursor_to_cell(cur, grid, "out")
    # ONE shift-click on the output crafts everything the grid holds (`count` per
    # cell = `count` crafts) and lands it in the inventory -- tools in the hotbar,
    # stackables onto an existing stack. Nothing rides the cursor, so the take-then-
    # bank pair that lost every s1 product (the milestone-drop cleared the bank
    # click; a bank click that missed left the product on the cursor) is gone.
    acts += a + P.click("attack", shift=True)
    acts.append(macros.marker("_craftcheck", {
        "item": item, "product": product, "count": count, "out": out_n,
        "base": _stat(info, "craft_item", product), "grid": grid,
        "cells": sorted(int(c) for c in cells), "t": 0}, 4))
    return _charge(acts), (f"crafting {count}x {item} in the {grid} grid"
                           + (f" ({short})" if short else ""))


# -- place and open ---------------------------------------------------------

def _hotbar_dest(info: dict) -> tuple[int | None, bool]:
    """(hotbar slot to put a block in, whether it is occupied). Empty first; else a
    slot holding a stackable non-tool block that can be swapped out."""
    for s in range(9):
        if _slot_item(info, s)[0] is None:
            return s, False
    for s in range(8, -1, -1):
        t, _ = _slot_item(info, s)
        if t is not None and not is_tool(t):
            return s, True
    return None, False


def ensure_hotbar(cur, info: dict, item: str, label: str
                  ) -> tuple[list[dict[str, Any]], int, str]:
    """(entries, hotbar slot 0-8, error) that leave a stack of `item` in the hotbar:
    nothing to do when it is there; otherwise one inventory trip (open, lift, drop it
    into an empty hotbar slot -- or swap with a stackable non-tool -- close)."""
    from mcu_worldmodel import procedures as P

    stacks = gui.find_slots(info, item)
    if not stacks:
        return [], -1, f"{label}: you carry no {item}."
    hot = [s for s, _ in stacks if s <= 8]
    if hot:
        return [], hot[0], ""
    if _screen_is_open(cur, info):
        return [], -1, (f"{label}: the {item} is not in the hotbar and a screen is open "
                        f"-- close_inventory first, then call it again (the macro moves "
                        f"it to the hotbar itself).")
    src0 = stacks[0][0]
    dest, occupied = _hotbar_dest(info)
    if dest is None:
        return [], -1, (f"{label}: no hotbar slot can take the {item} (all nine hold "
                        f"tools) -- discard or move one first.")
    acts: list[dict[str, Any]] = []
    a, _ = P.open_screen(cur)
    acts += a
    acts.append(macros.marker("_screen_need", {"kind": "inventory", "label": label}, 0))
    a, _ = P.cursor_to_slot(cur, src0)
    acts += a + P.click("attack")                           # lift the stack
    a, _ = P.cursor_to_slot(cur, dest)
    acts += a + P.click("attack")                           # into the hotbar (or swap)
    if occupied:
        a, _ = P.cursor_to_slot(cur, src0)
        acts += a + P.click("attack")                       # the swapped stack back
    a, _ = P.close_screen(cur)
    acts += a
    return _charge(acts), dest, ""


def place_and_open(cur, info: dict, item: str = "crafting_table"
                   ) -> tuple[list[dict[str, Any]], str]:
    """Put a carried table/furnace on the ground one block ahead and open its screen:
    hotbar transfer if needed (one GUI trip), select it, aim 55 degrees down, place
    (verified on `use_item`), right-click it until the screen is up, verify the kind."""
    from mcu_worldmodel import procedures as P

    item = str(item)
    if item not in ("crafting_table", "furnace"):
        return [], f"place_and_open: item must be crafting_table or furnace, not {item!r}"
    if not gui.find_slots(info, item):
        return [], f"place_and_open: you carry no {item} -- craft one first (craft())."
    acts, src, err = ensure_hotbar(cur, info, item, f"place_and_open({item})")
    if err:
        return [], err
    acts += P.equip_hotbar(src + 1)
    acts += P.look_abs(pitch=PLACE_PITCH, ticks=20)
    acts += P.click("use", hold=1, gui=False)
    acts.append(macros.marker("_placecheck", {
        "item": item, "base": _stat(info, "use_item", item), "t": 0}, 4))
    acts += P.use_until_gui(4)
    acts.append(macros.marker("_screen_need", {
        "kind": "table" if item == "crafting_table" else "furnace",
        "label": f"place_and_open({item})", "opened": True}, 0))
    # The projection follows what the plan will have done: the block's screen is
    # up, so a `craft` / `furnace_load` later in the SAME plan compiles (the runtime
    # gate above still refuses it if the screen did not in fact open).
    if not cur.is_open:
        cur.opened(cur.current)
    return _charge(acts), (f"placing the {item} from hotbar {src + 1} on the ground ahead and "
                  f"opening it")


# -- furnace ----------------------------------------------------------------

def _pick_fuel(info: dict, fuel: str, n_items: int) -> tuple[str, int, str]:
    """(fuel ingredient, units to load, why-not). `fuel='auto'` takes the best fuel
    carried; a named fuel is used as given."""
    alias = {"planks": "@planks", "logs": "@logs", "log": "@logs", "plank": "@planks"}
    cands = (list(FUEL_AUTO) if fuel in ("auto", "", None)
             else [alias.get(str(fuel), str(fuel))])
    for f in cands:
        per = FUEL_PER_UNIT.get(f, 1.0)
        units = max(1, int(math.ceil(n_items / per)))
        have = sum(q for _, q in gui.find_slots(info, f))
        if have >= units:
            return f, units, ""
        if have > 0 and fuel not in ("auto", "", None):
            return f, have, ""      # a named fuel that is short still gets loaded
    return "", 0, ("no fuel carried (coal, charcoal, planks, logs or sticks)"
                   if fuel in ("auto", "", None) else f"no {fuel} carried")


def furnace_load(cur, info: dict, item: str = "iron_ore", n: int = 0,
                 fuel: str = "auto") -> tuple[list[dict[str, Any]], str]:
    """Load the open furnace: `n` of `item` (0 = the whole stack) into the smelt cell
    and enough fuel below it (auto: coal > charcoal > planks > logs > sticks). It does
    not wait -- smelting takes ~200 ticks per item whether you watch it or not."""
    from mcu_worldmodel import procedures as P

    item = str(item)
    try:
        n = max(0, int(n))
    except (TypeError, ValueError):
        return [], f"furnace_load: bad n {n!r}"
    if not _screen_is_open(cur, info):
        return [], ('furnace_load: no screen is open -- place_and_open(item="furnace") '
                    'first, or use_at your placed furnace.')
    stacks = gui.find_slots(info, item)
    if not stacks:
        return [], f"furnace_load: you carry no {item}."
    src, qty = stacks[0]
    n = qty if n == 0 or n > qty else n
    fuel_name, units, why = _pick_fuel(info, str(fuel), n)
    if not fuel_name:
        return [], f"furnace_load: {why}."
    fstacks = gui.find_slots(info, fuel_name)
    fsrc, fqty = fstacks[0]
    if fsrc == src:
        return [], f"furnace_load: {item} cannot fuel itself -- name a different fuel."
    units = min(units, fqty)
    label = f"furnace_load({item})"
    acts: list[dict[str, Any]] = [macros.marker("_screen_need", {
        "kind": "furnace", "label": label, "snap_inv": True}, 0)]
    a, _ = P.cursor_to_slot(cur, src)
    acts += a + P.click("attack")                           # lift the ore
    a, _ = P.cursor_to_cell(cur, "furnace", 0)
    acts += a
    if n >= qty:
        acts += P.click("attack")                           # the whole stack in
    else:
        for _ in range(n):
            acts += P.click("use")
        a, _ = P.cursor_to_slot(cur, src)
        acts += a + P.click("attack")                       # remainder back
    a, _ = P.cursor_to_slot(cur, fsrc)
    acts += a + P.click("attack")                           # lift the fuel
    a, _ = P.cursor_to_cell(cur, "furnace", 1)
    acts += a
    if units >= fqty:
        acts += P.click("attack")
    else:
        for _ in range(units):
            acts += P.click("use")
        a, _ = P.cursor_to_slot(cur, fsrc)
        acts += a + P.click("attack")
    acts.append(macros.marker("_furnacecheck", {
        "label": label, "item": item, "n": n, "fuel": fuel_name.lstrip("@"),
        "units": units, "t": 0}, 4))
    return _charge(acts), (f"loading the furnace with {n} {item} and {units} "
                  f"{fuel_name.lstrip('@')}; ~{200 * n} ticks to smelt -- go mine, "
                  f"then furnace_take()")


def furnace_take(cur, info: dict, item: str = "", slot: Any = None
                 ) -> tuple[list[dict[str, Any]], str]:
    """Take what the open furnace has finished (the output cell) and bank it. Stops
    with a note, without clicking, when the output cell is visibly empty."""
    from mcu_worldmodel import procedures as P

    item = str(item or "")
    if not _screen_is_open(cur, info):
        return [], ("furnace_take: no screen is open -- use_at your furnace first.")
    target, why = deposit_slot(info, item or "smelted", 64 if not item else 8, slot)
    if target is None:
        return [], f"furnace_take: nowhere to bank the output -- {why}"
    label = "furnace_take()"
    acts: list[dict[str, Any]] = [
        macros.marker("_screen_need", {"kind": "furnace", "label": label,
                                       "snap_inv": True}, 0),
        macros.marker("_outcheck", {"label": label, "t": 0}, 3)]
    a, _ = P.cursor_to_cell(cur, "furnace", "out")
    acts += a + P.click("attack", shift=True)              # quick-move: straight to a slot
    acts.append(macros.marker("_invcheck", {"label": label, "item": item,
                                            "slot": target, "t": 0}, 4))
    return _charge(acts), "taking the furnace output"


# -- drop a stack and pick it up again -----------------------------------------

def drop_and_pickup(cur, info: dict, slot: int = 0) -> tuple[list[dict[str, Any]], str]:
    """Throw the stack in `slot` on the floor and walk over it. The `pickup`
    statistic counts items picked up OFF THE GROUND only: what comes out of a
    furnace or a crafting grid is `craft_item` (measured; every live run
    that banked the iron_ingot milestone had dropped an ingot by accident first).
    A milestone written as `pickup X` for an X that was smelted or crafted needs
    exactly this. Lift, force-close (the game throws the cursor stack ~2 blocks
    ahead), walk onto it, sweep until the inventory count comes back."""
    from mcu_worldmodel import procedures as P

    try:
        sid = int(slot)
    except (TypeError, ValueError):
        return [], f"drop_and_pickup: bad slot {slot!r}"
    if not 0 <= sid <= 35:
        return [], f"drop_and_pickup: slot must be 0-35, not {sid}"
    name, qty = _slot_item(info, sid)
    if name is None:
        return [], f"drop_and_pickup: slot {sid} is empty -- name the slot from [INV]."
    if _screen_is_open(cur, info):
        return [], "drop_and_pickup: close the screen first (no screen open)."
    # Looking straight down, the thrown stack lands at the feet; a player-dropped
    # item has a 40-tick pickup delay and is then collected where it lies, without
    # a step. A level throw lands 2-3 blocks out and the first version's fixed walk
    # plus sweep missed it (a staged scene).
    acts = P.look_abs(pitch=90, ticks=20)
    a, _ = P.open_screen(cur)
    acts += a
    acts.append(macros.marker("_screen_need", {"kind": "inventory",
                                               "label": "drop_and_pickup"}, 0))
    a, err = P.cursor_to_slot(cur, sid)
    if err:
        return [], err
    acts += a + P.click("attack")                           # lift the stack
    a, _ = P.close_screen(cur, force=True)                  # thrown at the feet
    acts += a
    acts.append(macros.marker("_droppick", {"item": name, "qty": qty, "t": 0,
                                            "budget": DROPPICK_TICKS}, DROPPICK_TICKS))
    return _charge(acts), (f"dropping {qty} {name} at your feet and picking it up "
                           f"again so the game counts a `pickup`")


#: Ticks drop_and_pickup waits for the stack to come back: the 40-tick pickup delay,
#: then a short shuffle in case it rolled off the block.
DROPPICK_TICKS = 110
_DROPPICK_SHUFFLE = (("forward", 5), ("back", 10), ("forward", 5), ("left", 5),
                     ("right", 10), ("left", 5))


@macros.tick("_droppick", shrink="budget")
def _droppick_tick(agent, dp: dict[str, Any], mk_act):
    """Wait for the thrown stack to be picked up again; shuffle after the delay."""
    item, qty = dp["item"], int(dp["qty"])
    if dp.get("base") is None:
        dp["base"] = int(agent._cur_inv.get(item, 0))
        dp["pick0"] = agent.stat_now("pickup", item)
    have = int(agent._cur_inv.get(item, 0))
    picked = agent.stat_now("pickup", item) - float(dp["pick0"])
    if have >= dp["base"] + qty or picked >= qty:
        agent.cursor_stats["drop_pickups"] = agent.cursor_stats.get("drop_pickups", 0) + 1
        agent.memory.add_note(
            f"drop_and_pickup: {qty} {item} back in the inventory after {dp['t']} "
            f"ticks -- `pickup {item}` +{picked:g} registered.")
        return None
    t = dp["t"]
    dp["t"] += 1
    if t >= dp["budget"]:
        agent._note_failure("drop_and_pickup")
        agent.memory.add_note(
            f"drop_and_pickup: the {item} did not come back in {t} ticks (pickup "
            f"+{picked:g}, you carry {have}). It lies within a block or two of where "
            f"you stand -- collect_drops here, or look down and check the frame.")
        return None
    if t < 48:
        return mk_act()                      # the pickup delay: stand on it
    p = (t - 48) % 40
    key = "forward"
    for k, n in _DROPPICK_SHUFFLE:
        if p < n:
            key = k
            break
        p -= n
    return mk_act(**{key: 1})


# -- mine until an item lands -------------------------------------------------

def mine_until(item: str = "flint", n: int = 1, ticks: int = 240
               ) -> list[dict[str, Any]]:
    """Hold attack on what the crosshair is on until `n` more `item` are in the
    inventory (flint from gravel: about one block in ten) or `ticks` run out."""
    from mcu_worldmodel import procedures as P

    t = max(20, min(400, int(ticks)))
    out = P._mine_seq(P.repeat(P.act(attack=1), t), False)
    out[0]["_seq"].update({"label": f"mine_until({item})", "until_item": str(item),
                           "until_n": max(1, int(n)), "base_n": None})
    return out


# -- the runner side: tick functions ------------------------------------------

def _scratch(agent) -> dict[str, Any]:
    return agent.__dict__.setdefault("_macro_scratch", {})


def _bucket(agent, event: str) -> dict[str, float]:
    """The cumulative statistics of one event as of the last observe."""
    raw = (agent.ledger._prev or {}).get(event)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v.item()) if hasattr(v, "item") else float(v)
        except (TypeError, ValueError):
            continue
    return out


def product_matches(key: str, product: str) -> bool:
    """Whether a statistic key counts as `product`: the recipe says `planks`, the
    statistic says `oak_planks`; `charcoal_torch` makes `torch`."""
    return key == product or key.endswith("_" + product)


def stat_gain(agent, event: str, product: str, base: dict[str, float]) -> float:
    now = _bucket(agent, event)
    return sum(v - base.get(k, 0.0) for k, v in now.items() if product_matches(k, product))


@macros.tick("_later")
def _later_tick(agent, lt: dict[str, Any], mk_act):
    """Expand a macro the parser deferred (procedures.DEFERRABLE), now that the entries
    before it have run: compile it against the live inventory, screen and cursor and
    splice its entries in right behind this marker, under the same plan entry. If it
    is still refused, its note is the honest one for THIS state."""
    from mcu_worldmodel import procedures as P

    name, args = str(lt.get("name", "")), dict(lt.get("args") or {})
    info = agent._cur_info or {}
    expanded, note = P.expand(name, info=info, cursor=agent.cursor.copy(), **args)
    if expanded:
        idx = agent.queue[0][1] if agent.queue else 0
        for step in reversed(expanded):
            agent.queue.insert(1, (step, idx))
        agent.cursor_stats["deferred_expanded"] = (
            agent.cursor_stats.get("deferred_expanded", 0) + 1)
        return None
    agent.cursor_stats["deferred_refused"] = agent.cursor_stats.get("deferred_refused", 0) + 1
    agent._note_failure(name)
    agent.memory.add_note(note or f"{name}: still not possible when its turn came.")
    return None


@macros.tick("_screen_need")
def _screen_need_tick(agent, sn: dict[str, Any], mk_act):
    """Zero-cost gate at the head of a GUI macro: the right screen is open, the cells
    it will fill are empty. Also the place where a verification baseline is taken --
    at run time, so an earlier entry of the same plan cannot pre-satisfy the check."""
    from mcu_worldmodel import vision
    import numpy as np

    label = sn.get("label", "gui macro")
    family = label.split("(")[0]
    if not agent._gui_open:
        agent._note_failure(family)
        agent._flush_tail(
            f"{label}: no screen is open"
            + (" -- the right-click did not open the block's screen; make sure the "
               "crosshair is on it (look_at) and that the selected item is not a "
               "placeable block." if sn.get("opened") else
               ". Open the screen first (open_inventory for a 2x2 recipe; place_and_open "
               "or use_at for a table / furnace)."),
            "screen_need_flush")
        return None
    kind, have = sn.get("kind", "any"), agent._screen
    if kind != "any" and have is not None and have != kind:
        agent._note_failure(family)
        agent._flush_tail(
            f"{label} needs the {kind} screen, but the open screen is the {have}. "
            f"close_inventory, then open the right one"
            + (" (place_and_open(item=\"crafting_table\") or use_at your table)."
               if kind == "table" else
               " (place_and_open(item=\"furnace\") or use_at your furnace)."
               if kind == "furnace" else " (open_inventory)."),
            "screen_kind_flush")
        return None
    cells = sn.get("cells_clear") or []
    if cells and agent._last_pov is not None:
        frame = np.asarray(agent._last_pov)
        ox, oy = gui.container_origin(*agent.cursor.render)
        busy = [i for i, tl in enumerate(cells)
                if vision.slot_occupied(frame, int(ox + tl[0]), int(oy + tl[1]))]
        if busy:
            grid = sn.get("grid", "3x3")
            agent._note_failure(family)
            agent._flush_tail(
                f"{label}: {len(busy)} of the recipe's cells already hold something "
                f"(leftovers from an earlier craft). Bank them first: stow_items("
                f"grid=\"{grid}\", cells=[...]) with the cell numbers from the [GRID] "
                f"line, then call {label} again.", "cells_busy_flush")
            return None
    sc = _scratch(agent)
    if sn.get("base_event"):
        sc[sn["base_event"]] = _bucket(agent, sn["base_event"])
    if sn.get("snap_inv"):
        sc["inv"] = dict(agent._cur_inv)
    return None


@macros.tick("_craftcheck")
def _craftcheck_tick(agent, ck: dict[str, Any], mk_act):
    """Did `craft_item` move? Waits a few ticks for the GUI's own tick, then says so
    either way; a failure drops the rest of the plan."""
    product = ck.get("product", ck["item"])
    base = _scratch(agent).get("craft_item")
    if base is None:
        base = {product: float(ck["base"])}
    gained = stat_gain(agent, "craft_item", product, base)
    if gained > 0:
        have = sum(v for k, v in agent._cur_inv.items() if product_matches(k, product))
        if have <= 0 and ck.get("t2", 0) < 20:
            # The statistic moves well before the inventory observation shows the
            # product -- 6-15 ticks in a staged scene ("+1 stone_pickaxe
            # crafted (you now carry 0)" and the pickaxe listed two entries later).
            # Wait for it, so the note and the next entry see the real inventory.
            ck["t2"] = ck.get("t2", 0) + 1
            return mk_act()
        agent.cursor_stats["craft_ok"] = agent.cursor_stats.get("craft_ok", 0) + 1
        # Where the quick-move put it: a tool in the hotbar is what the model needs
        # to know to select it.
        inv = (agent.ledger._prev or {}).get("inventory") or {}
        where = ""
        for s in range(36):
            t, _q = _slot_item({"inventory": inv}, s)
            if t is not None and product_matches(t, product):
                where = f", in slot {s}" + (f" = hotbar {s + 1}" if s <= 8 else "")
                if s <= 8:
                    break
        agent.memory.add_note(
            f"craft({ck['item']}): +{gained:g} {product} crafted (you now carry "
            f"{have}{where})." + ("" if have > 0 else " The inventory listing is still "
                                  "catching up; it will show on the next line."))
        return None
    if ck["t"] < 4:
        ck["t"] += 1
        return mk_act()
    agent.cursor_stats["craft_failed"] = agent.cursor_stats.get("craft_failed", 0) + 1
    agent._note_failure("craft")
    # Clean up after itself: the ingredients this macro put into the cells go back
    # into the inventory NOW (stow_items on exactly those cells), so the drop guard
    # does not refuse every later close. One run laid a correct stone
    # pickaxe whose output never appeared, then sat 1,500+ steps behind "close
    # refused: cobblestonex3, stickx2 off-inventory" without ever stowing them.
    cleanup: list[dict[str, Any]] = []
    if ck.get("cells") and agent._gui_open:
        from mcu_worldmodel import procedures as P
        cleanup, _n = P.expand("stow_items", info=agent._cur_info or {},
                               cursor=agent.cursor.copy(), grid=ck["grid"],
                               cells=list(ck["cells"]))
    agent._flush_tail(
        f"craft({ck['item']}) produced NOTHING -- craft_item did not move (a click "
        f"missed, the screen was not the {ck['grid']} one, or the output never "
        f"appeared)."
        + (f" The runner is banking the {len(ck['cells'])} cells it filled back into "
           f"your inventory now; check [INV], then call craft again."
           if cleanup else
           f" Read the [GRID] line: stow_items(grid=\"{ck['grid']}\", cells=[...]) "
           f"banks whatever sits in the cells; then call craft again. If the screen "
           f"closed mid-way, reopen it first."),
        "craft_failed_flush")
    if cleanup:
        idx = agent.queue[0][1] if agent.queue else 0
        for step in reversed(cleanup):
            agent.queue.insert(1, (step, idx))
        agent.cursor_stats["craft_cleanup"] = agent.cursor_stats.get("craft_cleanup", 0) + 1
    return None


def placed_block(pos: dict | None) -> tuple[int, int, int] | None:
    """Where a block placed at PLACE_PITCH lands: the ray from the eye (1.62 up) at
    55 degrees down meets the feet plane 1.62 / tan(55) = 1.13 blocks ahead, on the
    ground block there -- the placed block is the air cell above it, at feet level.
    Same yaw convention as look_at: +x is -sin(yaw), +z is cos(yaw)."""
    import math
    if not pos:
        return None
    try:
        yaw = math.radians(float(pos["yaw"]))
        d = 1.62 / math.tan(math.radians(PLACE_PITCH))
        return (int(math.floor(float(pos["x"]) - math.sin(yaw) * d)),
                int(math.floor(float(pos["y"]))),
                int(math.floor(float(pos["z"]) + math.cos(yaw) * d)))
    except (KeyError, TypeError, ValueError):
        return None


@macros.tick("_placecheck")
def _placecheck_tick(agent, pc: dict[str, Any], mk_act):
    """Did the block go down (`use_item` moved)? A failed placement stops the entry
    before use_until_gui spends its presses on bare ground."""
    gained = agent.stat_now("use_item", pc["item"]) - float(pc["base"])
    if gained > 0:
        agent.cursor_stats["place_ok"] = agent.cursor_stats.get("place_ok", 0) + 1
        at = placed_block(agent._cur_pos)
        if at is not None:
            agent._placed[str(pc["item"])] = at
            grid = getattr(agent, "grid", None)
            if grid is not None:
                grid.mark_placed(agent.step, pc["item"], at, agent._cur_pos)
            agent.memory.add_note(
                f"placed the {pc['item']} at about {at} -- use_at(x={at[0]}, y={at[1]}, "
                f"z={at[2]}) opens it when you come back to it.")
        return None
    if pc["t"] < 4:
        pc["t"] += 1
        return mk_act()
    agent.cursor_stats["place_failed"] = agent.cursor_stats.get("place_failed", 0) + 1
    agent._note_failure("place_and_open")
    agent._flush_tail(
        f"place_and_open({pc['item']}): the {pc['item']} did not go down (use_item "
        f"unchanged). The block lands on the face under the crosshair, 55 degrees "
        f"down = the ground one block ahead: that spot must be solid with air above "
        f"it and not where you stand. Step back one block (or turn to flat ground) "
        f"and call it again.", "place_failed_flush")
    return None


@macros.tick("_furnacecheck")
def _furnacecheck_tick(agent, fc: dict[str, Any], mk_act):
    """After loading: the ore and the fuel must have LEFT the inventory (the gate's
    snapshot), and the smelt cell must show an item. The fuel cell is not read: the
    furnace consumes a fuel unit the instant smelting starts, so a load of exactly
    one coal leaves that cell empty while the fire burns (a staged scene --
    the frame check called every such load a missed click)."""
    from mcu_worldmodel import vision
    import numpy as np

    if fc["t"] < 3:
        fc["t"] += 1
        return mk_act()
    base = _scratch(agent).get("inv") or {}
    ore_gone = base.get(fc["item"], 0) - agent._cur_inv.get(fc["item"], 0)
    fuel_key = fc["fuel"]
    fuel_gone = sum(base.get(k, 0) - agent._cur_inv.get(k, 0)
                    for k in set(base) | set(agent._cur_inv)
                    if k == fuel_key or k.endswith("_" + fuel_key.rstrip("s")))
    frame = agent._last_pov
    inside = True
    if frame is not None:
        f = np.asarray(frame)
        ox, oy = gui.container_origin(*agent.cursor.render)
        inside = vision.slot_occupied(f, int(ox + gui.FURNACE_IN[0]),
                                      int(oy + gui.FURNACE_IN[1]))
    if ore_gone >= 1 and fuel_gone >= 1 and inside:
        agent.cursor_stats["furnace_loaded"] = (
            agent.cursor_stats.get("furnace_loaded", 0) + 1)
        agent.memory.add_note(
            f"{fc['label']}: {ore_gone:g} {fc['item']} in the smelt cell, {fuel_gone:g} "
            f"{fc['fuel']} in the fuel cell -- about {200 * ore_gone:g} ticks to finish. "
            f"Close the screen and do something useful; furnace_take() collects the "
            f"output (each take needs the furnace screen open again). NOTE: output "
            f"taken from a furnace counts as `craft_item`, not `pickup`.")
        return None
    missing = ("the fuel cell" if (ore_gone >= 1 and inside)
               else "the smelt cell" if fuel_gone >= 1 else "both cells")
    agent._note_failure("furnace_load")
    agent._flush_tail(
        f"{fc['label']}: {missing} read EMPTY after loading -- a click missed. Read "
        f"[GRID] and [CURSOR] (a stack riding the cursor?), bank it with a gui_click "
        f"on an empty slot, then call furnace_load again.", "furnace_load_flush")
    return None


@macros.tick("_outcheck")
def _outcheck_tick(agent, oc: dict[str, Any], mk_act):
    """The furnace output cell must visibly hold something before it is clicked."""
    from mcu_worldmodel import vision
    import numpy as np

    if oc["t"] < 1:
        oc["t"] += 1
        return mk_act()
    frame = agent._last_pov
    if frame is None:
        return None
    f = np.asarray(frame)
    ox, oy = gui.container_origin(*agent.cursor.render)
    if vision.slot_occupied(f, int(ox + gui.FURNACE_OUT[0]), int(oy + gui.FURNACE_OUT[1])):
        return None
    agent.cursor_stats["furnace_out_empty"] = (
        agent.cursor_stats.get("furnace_out_empty", 0) + 1)
    agent._flush_tail(
        f"{oc['label']}: the output cell is EMPTY -- nothing has finished smelting "
        f"(200 ticks per item; the [GRID] line shows whether the smelt/fuel cells "
        f"still hold something). Close the screen, work elsewhere, come back later.",
        "furnace_out_empty_flush")
    return None


@macros.tick("_invcheck")
def _invcheck_tick(agent, ic: dict[str, Any], mk_act):
    """What arrived in the inventory since the macro's gate snapshot."""
    if ic["t"] < 3:
        ic["t"] += 1
        return mk_act()
    base = _scratch(agent).get("inv") or {}
    gained = {k: v - base.get(k, 0) for k, v in agent._cur_inv.items()
              if v - base.get(k, 0) > 0}
    if gained:
        txt = ", ".join(f"{k} +{v}" for k, v in sorted(gained.items()))
        agent.cursor_stats["furnace_took"] = agent.cursor_stats.get("furnace_took", 0) + 1
        agent.memory.add_note(f"{ic['label']}: {txt} now in the inventory.")
        return None
    agent._note_failure("furnace_take")
    agent.memory.add_note(
        f"{ic['label']}: nothing arrived in the inventory. If [CURSOR] shows a stack "
        f"off-inventory the take click worked and the bank click missed: gui_click on "
        f"an empty slot. Otherwise the output cell was empty.")
    return None


# -- registration -------------------------------------------------------------

def register_all(register, Procedure) -> None:
    register(Procedure(
        "craft",
        "ONE call crafts a recipe from your real inventory: lifts each ingredient, "
        "right-clicks one into every cell, puts the remainder back, takes the output "
        "`count` times, banks it (tools go to the hotbar) and verifies craft_item. "
        "Writes a [NOTE] either way; a failed craft drops the rest of the plan.",
        craft, needs_cursor=True, needs_info=True,
        preconditions="The RIGHT screen must be open: open_inventory for a 2x2 recipe "
                      "(planks, sticks, table, torch, flint_and_steel, blaze_powder, "
                      "ender_eye), a crafting table's screen for a 3x3 one (pickaxes, "
                      "swords, furnace, bucket). Ingredients per the recipe list.",
        params={"item": "recipe name from the list", "count": "crafts to run (default 1; "
                "e.g. planks count=2 -> 8 planks)", "slot": "optional slot to bank into"}))
    register(Procedure(
        "place_and_open",
        "Put your crafting_table or furnace on the ground one block ahead and open its "
        "screen (moves it to the hotbar first if needed, verifies the placement on "
        "use_item and the screen kind). Follow with craft / furnace_load.",
        place_and_open, needs_cursor=True, needs_info=True,
        preconditions="Carry the block; face flat ground with no screen open. To reopen a "
                      "block already placed, use_at(its coordinates).",
        params={"item": "crafting_table or furnace"}))
    register(Procedure(
        "furnace_load",
        "Load the open furnace: n of item (0 = the whole stack) into the smelt cell and "
        "enough fuel into the fuel cell (auto picks coal > charcoal > planks > logs > "
        "sticks). Does not wait: ~200 ticks per item; close the screen and come back.",
        furnace_load, needs_cursor=True, needs_info=True,
        preconditions="The furnace screen must be open (place_and_open(item=\"furnace\") "
                      "or use_at on a placed one).",
        params={"item": "what to smelt (iron_ore, gold_ore, a log for charcoal...)",
                "n": "items to load, 0 = all (default)",
                "fuel": "auto (default) or a fuel item name"}))
    register(Procedure(
        "furnace_take",
        "Take the finished output out of the open furnace and bank it (checks the "
        "output cell is not empty first; reports what arrived).",
        furnace_take, needs_cursor=True, needs_info=True,
        preconditions="The furnace screen must be open. Nothing to take before ~200 "
                      "ticks per item have passed since loading.",
        params={"item": "expected output, e.g. iron_ingot (optional)",
                "slot": "optional slot to bank into"}))
    register(Procedure(
        "drop_and_pickup",
        "Throw the stack in `slot` on the floor and walk over it, so the game counts a "
        "`pickup` of it. Needed when a milestone says `pickup X` and X came out of a "
        "furnace or a crafting grid (those count as craft_item, never pickup).",
        drop_and_pickup, needs_cursor=True, needs_info=True,
        preconditions="No screen open; the slot id from [INV]. Clear ground ahead "
                      "(the stack lands ~2 blocks in front of you).",
        params={"slot": "0-35"}))
    register(Procedure(
        "mine_until",
        "Hold attack on the block under the crosshair until n more of `item` are in "
        "the inventory (flint out of GRAVEL: ~1 block in 10; keep the crosshair on the "
        "gravel bank -- falling gravel refills the spot), or until the ticks run out.",
        lambda item="flint", n=1, ticks=240: mine_until(item, n, ticks),
        preconditions="Aim first (look_at / look_abs); a pickaxe or shovel in hand.",
        params={"item": "item name to wait for", "n": "how many more (default 1)",
                "ticks": "budget, 20-400 (default 240)"}))
