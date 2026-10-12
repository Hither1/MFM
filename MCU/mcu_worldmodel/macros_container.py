"""One-call macros for the container screens: chests, brewing, enchanting, stonecutting.

Why these exist. `macros_gui` covers the two screens the diamond chain needs (a crafting
table and a furnace) and nothing else, so every other container in the benchmark -- "explore
the contents of a chest", the buried-treasure tasks, "brew a potion of fire resistance",
"enchant a diamond sword", "cut stone" -- was hundreds of blind cursor ticks per turn, on a
screen `vision.screen_kind` could not even name (a chest read as None, a brewing stand and a
stonecutter both read as "furnace"). One human click each; hundreds of model steps here.

What made them addressable is measured in `gui.py`: the container is CENTRED, so a chest
(176x168) and a double chest (176x222) are drawn shifted against the fixed 176x166 frame the
cursor works in, and every constant there already carries that shift. `vision.screen_kind`
tells the six screens apart on their SLOT LAYOUT rather than on their contents -- a slot's
dark top/left and white bottom/right bevels are background texture that an item icon is
drawn inside, so the reading is the same for a full stack and an empty cell.

Two things are different from `macros_gui` and are the reason for the extra machinery here:

* **Chest contents are only knowable at run time.** At plan time a macro sees `info`, which
  covers the 36 player slots and nothing else; which of a chest's 27 (or 54) cells hold
  something is in the frame. So `container_take` / `container_put` emit ONE marker that
  reads the frame and *splices* the servo/click pairs it needs into the queue behind itself
  (`_splice`), as part of the same plan entry.
* **Everything moves by quick-move (`click(shift=True)`).** Measured in the sim on
  a shift-click empties a chest cell into the inventory, and a shift-click on a
  player slot routes an item to the cell of the open screen that accepts it -- a potion to a
  brewing stand's bottle slots, blaze powder to its fuel slot, nether wart or magma cream to
  its ingredient slot, lapis to the enchanting table's lapis slot, anything else to its item
  slot, stone to the stonecutter's input. Nothing rides the cursor afterwards, so no close
  can drop it and no bank click can miss.

Engine facts measured in a staged scene (41 checks):

* Container heights, from the top bevel row on the centre column: a chest or barrel is 168
  (top row 96), a double chest 222 (top row 69), every other screen 166 (top row 97).
* **Every potion, water bottles included, reports as `potion`** in `info['inventory']` --
  no NBT reaches the observation, so the harness cannot tell fire resistance from water.
  Only the ingredient order can: water bottle + nether_wart -> awkward, + magma_cream ->
  fire resistance, 400 ticks each. The full chain ran here and returned 3 potions.
* **Enchanting fires on a plain GUI click of an option button.** Nothing observable changes
  on the item: an enchanted diamond sword still reports as `diamond_sword`. The lapis count
  is the only channel that says the enchantment applied (6 -> 5 for option 1), so that is
  what `_enchcheck` verifies.
* **A quick-move on the stonecutter's result is craft-ALL** (the handler loops the transfer
  until the input stops producing), which is why `stonecut` loads one item per attempt while
  it is searching and the whole stack once the button is known. From `stone` the buttons
  offered are, in order: 0 chiseled_stone_bricks, 1 stone_brick_slab, 2 stone_brick_stairs,
  3 stone_brick_wall. Plain `stone_bricks` is NOT a stonecutter recipe (it is the 2x2 craft).
* Each half of a double chest is its OWN block entity with its own `container.0-26`; the
  screen stacks one half's 27 cells above the other's.
* An anvil is RECOGNISED (`screen_kind` -> "anvil") but has no macro: its only function that
  is not a craft is renaming, which needs a text field, and the action space has no keyboard.
* `macros.KEEPS_CONTENTS` gains chest, chest2 and brewing -- block-entity storage that
  survives a close. The enchanting table and the stonecutter are deliberately NOT added:
  their slots are screen-handler inventories, and Minecraft empties them on close (into the
  player inventory when there is room). The macros here take their cells back out themselves
  so the close is clean either way.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from mcu_worldmodel import gui, macros, vision
# The conventions the model macros already use: SERVO_CHARGE-capped cursor entries, the
# per-plan scratch space a gate marker snapshots into, and the statistics helper.
from mcu_worldmodel.macros_gui import SERVO_CHARGE, _bucket, _charge, _scratch, _slot_item

#: Screen kinds whose cells this module's chest macros address.
CHEST_KINDS = ("chest", "chest2")
#: Blocks that keep what sits in their cells when the screen closes: block-entity
#: storage. The enchanting table and the stonecutter are screen-handler inventories and
#: are emptied on close, so they must not be listed here.
macros.KEEPS_CONTENTS.update({"chest", "chest2", "brewing"})

#: What one addressed cell costs the plan's step cap: a cursor entry (charged
#: SERVO_CHARGE) plus a two-tick click and its release.
CELL_TICKS = SERVO_CHARGE + 3
#: Ticks a brew of one ingredient takes in Minecraft 1.16. Not waited for in a macro.
BREW_TICKS = 400
#: Names the engine may give a water bottle / a brewed potion in `info['inventory']`.
#: Measured in the sim: every potion, water bottles included, reports as `potion` with
#: no NBT, so the harness cannot tell fire resistance from water -- only the sequence
#: of ingredients you brewed can.
POTION_NAMES = ("potion", "water_bottle", "splash_potion", "lingering_potion")


# -- shared plumbing ---------------------------------------------------------

def _splice(agent, entries: list[dict[str, Any]]) -> None:
    """Queue `entries` immediately behind the marker that is running.

    They belong to the SAME plan entry (they carry its index), so the entry-done log,
    `_flush_tail` and the repeat-plan detector all keep treating the macro as one call.
    This is the seam a container macro needs and a crafting macro does not: which chest
    cells hold something, and where the player rows are drawn (a double chest moves them
    27 px down), are facts of the frame and of `agent._screen`, and neither exists at
    plan time.
    """
    if not agent.queue:
        return
    idx = agent.queue[0][1]
    for i, e in enumerate(entries, start=1):
        agent.queue.insert(i, (e, idx))


def _screen_is_open(cur, info: dict) -> bool:
    return bool(getattr(cur, "is_open", False)) or bool(info.get("isGuiOpen", False))


def _gate(label: str, kinds: tuple[str, ...], what: str) -> dict[str, Any]:
    """The zero-cost `_cscreen` marker every macro here starts with."""
    return macros.marker("_cscreen", {"label": label, "kinds": list(kinds),
                                      "what": what, "snap_inv": True}, 0)


def _chest_kind(agent) -> str:
    return agent._screen if agent._screen in CHEST_KINDS else "chest"


def _free_slots(agent) -> int:
    """Empty player slots, read from the last observation."""
    inv = (agent.ledger._prev or {}).get("inventory") or {}
    return sum(1 for s in range(36) if _slot_item({"inventory": inv}, s)[0] is None)


def _occupied(agent, cells: list[tuple[int, int]]) -> list[int]:
    """Indices of `cells` (container coordinates) that visibly hold an item."""
    frame = agent._last_pov
    if frame is None:
        return []
    f = np.asarray(frame)
    ox, oy = gui.container_origin(*agent.cursor.render)
    return [i for i, tl in enumerate(cells)
            if vision.slot_occupied(f, int(ox + tl[0]), int(oy + tl[1]))]


def _quick_move(cur, target: tuple[float, float], label: str) -> list[dict[str, Any]]:
    """Cursor onto `target`, then a quick-move click, advancing the PLAN-TIME projection."""
    from mcu_worldmodel import procedures as P

    if cur is not None:
        cur.pos = target
    return [P._servo(target, label)] + P.click("attack", shift=True)


def _run_move(target: tuple[float, float], label: str) -> list[dict[str, Any]]:
    """The same pair, spliced at RUN time. `cur=None` deliberately: the real cursor is
    re-measured from every frame, and writing a believed position into it would let a
    servo declare arrival on a frame where the arrow was not found."""
    return _quick_move(None, target, label)


def _park(agent, kind: str) -> list[dict[str, Any]]:
    """Move the pointer off the cells so the verification can read them.

    Not cosmetic: the arrow is drawn over the cell it sits on and `slot_occupied` reads
    texture, so the last cell a macro clicked reports FULL for ever after."""
    from mcu_worldmodel import procedures as P

    return [P._servo(gui.cursor_park(kind), "clear of the cells")]


def _names(items: Any) -> list[str]:
    """`items` as a list of item names; "all"/""/None mean no filter."""
    if items is None:
        return []
    if isinstance(items, str):
        if items.strip().lower() in ("", "all", "*", "everything"):
            return []
        return [s.strip() for s in items.split(",") if s.strip()]
    try:
        return [str(s).strip() for s in items if str(s).strip()]
    except TypeError:
        return []


def _writeoff(agent, item: str, n: int) -> None:
    """Take `n` of `item` off the cursor's screen-open baseline: the game CONSUMED it.

    Same move `CursorState.crafted` makes for a recipe, for the same reason. Enchanting
    eats lapis and a stonecutter eats its input, and neither has a statistic; without
    this the difference reads as "off-inventory, would drop on the floor" and every
    close_inventory after an enchant or a cut is refused (measured, a staged scene:
    "close refused: lapis_lazulix1", "close refused: stonex4").
    """
    if n <= 0 or agent.cursor.baseline is None:
        return
    have = agent.cursor.baseline.get(item, 0)
    if have:
        agent.cursor.baseline[item] = max(0, have - int(n))
        agent.cursor_stats["container_writeoffs"] = (
            agent.cursor_stats.get("container_writeoffs", 0) + 1)


def _gain(agent) -> dict[str, int]:
    """What has arrived in the inventory since the gate marker's snapshot."""
    base = _scratch(agent).get("inv") or {}
    return {k: v - base.get(k, 0) for k, v in agent._cur_inv.items()
            if v - base.get(k, 0) > 0}


def _lost(agent) -> dict[str, int]:
    base = _scratch(agent).get("inv") or {}
    return {k: was - agent._cur_inv.get(k, 0) for k, was in base.items()
            if was - agent._cur_inv.get(k, 0) > 0}


@macros.tick("_cscreen")
def _cscreen_tick(agent, sn: dict[str, Any], mk_act):
    """The gate: the right container screen is open, and the verification baseline is
    taken HERE, at run time, so an earlier entry of the same plan cannot pre-satisfy it."""
    label = sn.get("label", "container macro")
    family = label.split("(")[0]
    kinds = tuple(sn.get("kinds") or ())
    what = sn.get("what", "block")
    if not agent._gui_open:
        agent._note_failure(family)
        agent._flush_tail(
            f"{label}: no screen is open. Stand within ~4 blocks of the {what}, "
            f"look_at its exact coordinates, then use_until_gui -- and hold a "
            f"NON-PLACEABLE item first (equip_hotbar on a pickaxe or a torch): with a "
            f"block selected the right-click places the block instead of opening the "
            f"screen.", "container_no_screen")
        return None
    have = agent._screen
    if kinds and have is not None and have not in kinds:
        agent._note_failure(family)
        agent._flush_tail(
            f"{label} needs the {' or the '.join(kinds)} screen, but the open screen is "
            f"the {have}. close_inventory, then look_at the {what} and use_until_gui.",
            "container_wrong_screen")
        return None
    sc = _scratch(agent)
    if sn.get("snap_inv"):
        sc["inv"] = dict(agent._cur_inv)
    if sn.get("base_event"):
        sc[sn["base_event"]] = _bucket(agent, sn["base_event"])
    return None


@macros.tick("_ccheck")
def _ccheck_tick(agent, ck: dict[str, Any], mk_act):
    """Generic end-of-macro verification: what arrived in the inventory, and what the
    named cells still hold.

    It waits for the gain rather than a fixed number of ticks, because the inventory
    observation lags a GUI click by up to ~15 (a staged scene) and a single-cell
    take checked at a fixed 8 called every success a miss (a staged scene)."""
    gained = _gain(agent)
    if not gained and ck["t"] < int(ck.get("wait", 18)):
        ck["t"] += 1
        return mk_act()
    label = ck["label"]
    want = [w for w in (ck.get("want") or []) if w]
    left = len(_occupied(agent, [tuple(c) for c in (ck.get("cells") or [])]))
    txt = ", ".join(f"{k} +{v}" for k, v in sorted(gained.items())) or "nothing"
    if gained:
        agent.cursor_stats[ck.get("stat", "container_took")] = (
            agent.cursor_stats.get(ck.get("stat", "container_took"), 0) + 1)
        missing = [w for w in want if w not in gained]
        note = f"{label}: {txt} now in the inventory."
        if ck.get("cells"):
            note += (f" {left} of the {len(ck['cells'])} cells still hold something."
                     if left else " Every cell read is empty now.")
        if missing:
            note += (f" You asked for {', '.join(missing)} and none arrived -- a chest "
                     f"cell does not say what is in it, only that it is full, so take "
                     f"the rest and read [INV].")
        if ck.get("tail"):
            note += " " + ck["tail"]
        agent.memory.add_note(note)
        return None
    agent._note_failure(label.split("(")[0])
    agent.memory.add_note(
        f"{label}: NOTHING arrived in the inventory. Read [GRID] for what the cells hold "
        f"and [CURSOR] for a stack riding the pointer (gui_click on an empty inventory "
        f"slot banks it). If the cells are still full the quick-moves missed: your "
        f"inventory may be full, or the screen closed mid-way.")
    return None


# -- chests, barrels, double chests -------------------------------------------

def container_take(cur, info: dict, items: Any = "all", max_stacks: int = 27
                   ) -> tuple[list[dict[str, Any]], str]:
    """Empty the open chest into your inventory: quick-move every cell that visibly
    holds something, up to `max_stacks`, and report what arrived."""
    if not _screen_is_open(cur, info):
        return [], ("container_take: no screen is open -- stand next to the chest, "
                    "look_at its coordinates and use_until_gui first.")
    try:
        max_stacks = max(1, min(54, int(max_stacks)))
    except (TypeError, ValueError):
        return [], f"container_take: bad max_stacks {max_stacks!r}"
    wanted = _names(items)
    label = f"container_take({','.join(wanted) if wanted else 'all'})"
    budget = CELL_TICKS * max_stacks + 12
    acts = [_gate(label, CHEST_KINDS, "chest"),
            macros.marker("_ctake", {"label": label, "items": wanted,
                                     "budget": budget, "t": 0}, budget)]
    return acts, ("emptying the open chest into your inventory"
                  + (f", looking for {', '.join(wanted)}" if wanted else ""))


@macros.tick("_ctake", shrink="budget")
def _ctake_tick(agent, ct: dict[str, Any], mk_act):
    """Read which cells hold something, then queue one quick-move per full cell."""
    if agent._last_pov is None:
        if ct["t"] < 3:
            ct["t"] += 1
            return mk_act()
        agent._flush_tail(f"{ct['label']}: no frame to read the chest cells from.",
                          "container_no_frame")
        return None
    kind = _chest_kind(agent)
    cells = gui.chest_cells(kind)
    full = _occupied(agent, cells)
    if not full:
        agent.cursor_stats["container_empty"] = (
            agent.cursor_stats.get("container_empty", 0) + 1)
        agent.memory.add_note(
            f"{ct['label']}: the {kind} is EMPTY -- all {len(cells)} of its cells read "
            f"empty in the frame. Nothing to take; close_inventory and move on.")
        return None
    room = _free_slots(agent)
    if room <= 0:
        agent._note_failure("container_take")
        agent._flush_tail(
            f"{ct['label']}: your inventory is FULL and the chest still holds "
            f"{len(full)} stacks. discard_stack or container_put something first, then "
            f"call container_take again.", "container_inv_full")
        return None
    n = max(1, min(len(full), room, int(ct["budget"]) // CELL_TICKS))
    entries: list[dict[str, Any]] = []
    for i in full[:n]:
        entries += _run_move(gui.centre(cells[i]), f"chest cell {i}")
    entries += _park(agent, kind)
    tail = ""
    if n < len(full):
        tail = (f"{len(full) - n} cells were left (room for {room} stacks, budget for "
                f"{int(ct['budget']) // CELL_TICKS}) -- call container_take again.")
    entries.append(macros.marker("_ccheck", {
        "label": ct["label"], "cells": [list(c) for c in cells], "want": ct.get("items"),
        "wait": 18, "t": 0, "stat": "container_took", "tail": tail}, 10))
    _splice(agent, entries)
    return None


def container_put(cur, info: dict, item: str = "", n: int = 0
                  ) -> tuple[list[dict[str, Any]], str]:
    """Move `item` out of your inventory into the open chest (n = 0 moves every stack
    you carry; a smaller n moves exactly that many items into one empty cell)."""
    item = str(item or "")
    if not item:
        return [], 'container_put: name the item, e.g. container_put(item="cobblestone").'
    if not _screen_is_open(cur, info):
        return [], ("container_put: no screen is open -- look_at the chest and "
                    "use_until_gui first.")
    try:
        n = max(0, int(n))
    except (TypeError, ValueError):
        return [], f"container_put: bad n {n!r}"
    stacks = gui.find_slots(info, item)
    if not stacks:
        return [], f"container_put: you carry no {item}."
    have = sum(q for _, q in stacks)
    label = f"container_put({item})"
    budget = CELL_TICKS * min(6, len(stacks)) + 4 * CELL_TICKS + 12
    acts = [_gate(label, CHEST_KINDS, "chest"),
            macros.marker("_cput", {"label": label, "item": item, "n": n,
                                    "slots": [[s, q] for s, q in stacks[:6]],
                                    "have": have, "t": 0}, budget)]
    return acts, (f"putting {'all ' + str(have) if n == 0 else n} {item} into the "
                  f"open chest")


@macros.tick("_cput")
def _cput_tick(agent, cp: dict[str, Any], mk_act):
    """Queue the quick-moves, with the player rows read at THIS screen's offset."""
    if agent._last_pov is None:
        if cp["t"] < 3:
            cp["t"] += 1
            return mk_act()
        agent._flush_tail(f"{cp['label']}: no frame to read the chest from.",
                          "container_no_frame")
        return None
    from mcu_worldmodel import procedures as P

    kind = _chest_kind(agent)
    cells = gui.chest_cells(kind)
    slots = [(int(s), int(q)) for s, q in cp["slots"]]
    n, item = int(cp["n"]), cp["item"]
    entries: list[dict[str, Any]] = []
    if n == 0 or n >= int(cp["have"]):
        moved = sum(q for _, q in slots)
        for s, _q in slots:
            entries += _run_move(gui.centre(gui.player_slot_topleft(s, kind)),
                                 f"inventory slot {s}")
    else:
        # A partial move needs a destination the quick-move cannot choose: lift the
        # stack, right-click n items into the first EMPTY cell, put the rest back.
        full = set(_occupied(agent, cells))
        empty = next((i for i in range(len(cells)) if i not in full), None)
        if empty is None:
            agent._note_failure("container_put")
            agent._flush_tail(
                f"{cp['label']}: every cell of the {kind} is full, so a partial stack "
                f"has nowhere to go. container_take something out first, or call "
                f"container_put with n=0 to quick-move whole stacks.", "container_no_cell")
            return None
        src, qty = slots[0]
        n = min(n, qty)
        moved = n
        src_tl = gui.centre(gui.player_slot_topleft(src, kind))
        # probe clicks: a lift is verified by `_cputcheck`, and the runner's own
        # lifted-nothing judgment cannot see one here -- it re-reads the source slot
        # from the frame, where the lifted stack is drawn ON the pointer that is still
        # over that slot, so it reads "still full" and clears the queue (a staged scene).
        entries += [P._servo(src_tl, f"inventory slot {src}")]
        entries += P.click("attack", probe=True)
        entries += [P._servo(gui.centre(cells[empty]), f"chest cell {empty}")]
        for _ in range(n):
            entries += P.click("use", probe=True)
        entries += [P._servo(src_tl, f"inventory slot {src}")]
        entries += P.click("attack", probe=True)
    entries += _park(agent, kind)
    entries.append(macros.marker("_cputcheck", {"label": cp["label"], "item": item,
                                                "want": moved, "t": 0}, 10))
    _splice(agent, entries)
    return None


@macros.tick("_cputcheck")
def _cputcheck_tick(agent, ck: dict[str, Any], mk_act):
    """The item must have LEFT the inventory (it is in the chest, which keeps it)."""
    gone = _lost(agent).get(ck["item"], 0)
    if not gone and ck["t"] < 18:
        ck["t"] += 1
        return mk_act()
    if gone > 0:
        agent.cursor_stats["container_put"] = (
            agent.cursor_stats.get("container_put", 0) + 1)
        agent.memory.add_note(
            f"{ck['label']}: {gone} {ck['item']} moved into the chest (you now carry "
            f"{agent._cur_inv.get(ck['item'], 0)}). A chest keeps its contents across a "
            f"close, so close_inventory is safe.")
        return None
    agent._note_failure("container_put")
    agent._flush_tail(
        f"{ck['label']}: no {ck['item']} left your inventory. The chest may be full "
        f"(read [GRID]: a chest holds 27 cells, a double chest 54), or the screen was "
        f"not a chest. Read [CURSOR] for a stack riding the pointer.",
        "container_put_failed")
    return None


# -- brewing ------------------------------------------------------------------

def _potion_slots(info: dict) -> list[int]:
    """Player slots holding a potion of any kind, water bottles included."""
    out = []
    for s in range(36):
        name, qty = _slot_item(info, s)
        if name and qty > 0 and name in POTION_NAMES:
            out.append(s)
    return out


def brew(cur, info: dict, ingredient: str = "nether_wart", bottles: int = 3,
         fuel: str = "blaze_powder") -> tuple[list[dict[str, Any]], str]:
    """Load the open brewing stand: `bottles` potions (or water bottles) from your
    inventory into the bottle cells, blaze powder into the fuel cell, one `ingredient`
    into the ingredient cell. It does NOT wait -- a brew takes 400 ticks."""
    if not _screen_is_open(cur, info):
        return [], ("brew: no screen is open -- look_at the brewing stand and "
                    "use_until_gui first.")
    ingredient = str(ingredient)
    try:
        bottles = max(0, min(3, int(bottles)))
    except (TypeError, ValueError):
        return [], f"brew: bad bottles {bottles!r}"
    ing = gui.find_slots(info, ingredient)
    if not ing:
        return [], (f"brew: you carry no {ingredient}. A fire-resistance potion is "
                    f"water bottle -> nether_wart (awkward) -> magma_cream, two brews of "
                    f"400 ticks each.")
    pots = _potion_slots(info)
    if bottles and not pots:
        return [], ("brew: you carry no water bottles (fill a glass_bottle at water, or "
                    "start from bottles you already have). Call brew(bottles=0) when the "
                    "bottles are already in the stand.")
    label = f"brew({ingredient})"
    acts: list[dict[str, Any]] = [_gate(label, ("brewing",), "brewing stand")]
    fuel_slots = gui.find_slots(info, fuel) if fuel and fuel != "none" else []
    if fuel_slots:
        acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(fuel_slots[0][0])),
                            f"inventory slot {fuel_slots[0][0]} ({fuel})")
    for s in pots[:bottles]:
        acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(s)),
                            f"inventory slot {s} (potion)")
    acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(ing[0][0])),
                        f"inventory slot {ing[0][0]} ({ingredient})")
    from mcu_worldmodel import procedures as _P
    acts.append(_P._servo(gui.cursor_park("brewing"), "clear of the cells"))
    acts.append(macros.marker("_brewcheck", {"label": label, "ingredient": ingredient,
                                             "bottles": bottles, "t": 0}, 12))
    return _charge(acts), (f"loading the brewing stand with {bottles} bottles and "
                           f"{ingredient}; {BREW_TICKS} ticks to brew -- do something "
                           f"else, then brew_take()")


@macros.tick("_brewcheck")
def _brewcheck_tick(agent, bc: dict[str, Any], mk_act):
    """The ingredient must have left the inventory and the stand's cells must read full.
    The FUEL cell is not required: the stand burns a blaze powder the moment brewing
    starts, exactly as a furnace consumes its fuel (a staged scene's furnace lesson)."""
    if bc["t"] < 8:
        bc["t"] += 1
        return mk_act()
    gone = _lost(agent).get(bc["ingredient"], 0)
    ing_in = bool(_occupied(agent, [gui.BREW_INGREDIENT]))
    n_bottles = len(_occupied(agent, gui.BREW_BOTTLES))
    if gone >= 1 and (ing_in or n_bottles):
        agent.cursor_stats["brew_loaded"] = agent.cursor_stats.get("brew_loaded", 0) + 1
        agent.memory.add_note(
            f"{bc['label']}: {gone} {bc['ingredient']} in the ingredient cell, "
            f"{n_bottles} bottle cells full. Brewing takes {BREW_TICKS} ticks and runs "
            f"whether the screen is open or not -- close_inventory, do something else "
            f"for {BREW_TICKS}+ ticks, reopen the stand and call brew_take(). The "
            f"inventory calls EVERY potion `potion`, so the harness cannot confirm which "
            f"one you made; the ingredient order does (water -> nether_wart = awkward, "
            f"awkward -> magma_cream = fire resistance).")
        return None
    agent._note_failure("brew")
    agent._flush_tail(
        f"{bc['label']}: the load did not take -- {bc['ingredient']} left the inventory "
        f"{gone} times and the stand shows {n_bottles} full bottle cells. Read [GRID] "
        f"for the brewing row. A brewing stand only accepts a valid ingredient in the "
        f"ingredient cell and a potion in the bottle cells; blaze powder is the only "
        f"fuel.", "brew_failed")
    return None


def brew_take(cur, info: dict) -> tuple[list[dict[str, Any]], str]:
    """Quick-move the three bottle cells of the open brewing stand into your inventory."""
    if not _screen_is_open(cur, info):
        return [], ("brew_take: no screen is open -- look_at the brewing stand and "
                    "use_until_gui first.")
    label = "brew_take()"
    acts: list[dict[str, Any]] = [_gate(label, ("brewing",), "brewing stand")]
    for i, tl in enumerate(gui.BREW_BOTTLES):
        acts += _quick_move(cur, gui.centre(tl), f"brewing bottle {i}")
    from mcu_worldmodel import procedures as _P
    acts.append(_P._servo(gui.cursor_park("brewing"), "clear of the cells"))
    acts.append(macros.marker("_ccheck", {
        "label": label, "cells": [list(c) for c in gui.BREW_BOTTLES], "want": [],
        "wait": 18, "t": 0, "stat": "brew_took",
        "tail": "Every potion is reported as `potion` with no name, so count them and "
                "track what you brewed yourself."}, 10))
    return _charge(acts), "taking the bottles out of the brewing stand"


# -- enchanting ---------------------------------------------------------------

def enchant(cur, info: dict, item: str = "diamond_sword", option: int = 1
            ) -> tuple[list[dict[str, Any]], str]:
    """Enchant `item` at the open enchanting table: item and lapis in, option button
    1-3 clicked, then the item and the leftover lapis taken back out."""
    item = str(item)
    if not _screen_is_open(cur, info):
        return [], ("enchant: no screen is open -- look_at the enchanting table and "
                    "use_until_gui first.")
    try:
        option = max(1, min(3, int(option)))
    except (TypeError, ValueError):
        return [], f"enchant: bad option {option!r} (1, 2 or 3)"
    it = gui.find_slots(info, item)
    if not it:
        return [], f"enchant: you carry no {item}."
    lap = gui.find_slots(info, "lapis_lazuli")
    if not lap:
        return [], ("enchant: you carry no lapis_lazuli. Option 1 costs 1 lapis and 1 "
                    "level, option 2 costs 2 and 2, option 3 costs 3 and 3.")
    if sum(q for _, q in lap) < option:
        return [], (f"enchant: option {option} costs {option} lapis_lazuli and you carry "
                    f"{sum(q for _, q in lap)}. Use a lower option or mine more lapis.")
    label = f"enchant({item})"
    acts: list[dict[str, Any]] = [_gate(label, ("enchanting",), "enchanting table")]
    acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(it[0][0])),
                        f"inventory slot {it[0][0]} ({item})")
    acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(lap[0][0])),
                        f"inventory slot {lap[0][0]} (lapis_lazuli)")
    target = gui.enchant_button_centre(option - 1)
    cur.pos = target
    from mcu_worldmodel import procedures as P
    acts += [P._servo(target, f"enchant option {option}")] + P.click("attack")
    acts += [P.noop() for _ in range(6)]           # the enchant applies on the next tick
    acts += _quick_move(cur, gui.centre(gui.ENCHANT_ITEM), "enchant item cell")
    acts += _quick_move(cur, gui.centre(gui.ENCHANT_LAPIS), "enchant lapis cell")
    acts.append(P._servo(gui.cursor_park("enchanting"), "clear of the cells"))
    acts.append(macros.marker("_enchcheck", {"label": label, "item": item,
                                             "option": option, "t": 0}, 12))
    return _charge(acts), (f"enchanting {item} with option {option} "
                           f"({option} lapis, {option} levels)")


@macros.tick("_enchcheck")
def _enchcheck_tick(agent, ec: dict[str, Any], mk_act):
    """Lapis is the observable. `info['inventory']` reports an enchanted diamond_sword as
    `diamond_sword` -- there is no NBT in the observation and no enchantment statistic --
    so the ONLY channel that says the button fired is the lapis it consumed."""
    if ec["t"] < 8:
        ec["t"] += 1
        return mk_act()
    spent = _lost(agent).get("lapis_lazuli", 0)
    back = agent._cur_inv.get(ec["item"], 0)
    if spent >= 1:
        _writeoff(agent, "lapis_lazuli", spent)
        agent.cursor_stats["enchant_ok"] = agent.cursor_stats.get("enchant_ok", 0) + 1
        agent.memory.add_note(
            f"{ec['label']}: option {ec['option']} fired -- {spent} lapis_lazuli and "
            f"{spent} experience levels spent, and the {ec['item']} is back in your "
            f"inventory (you carry {back}) with the enchantment on it. The inventory "
            f"observation carries no NBT, so it still reads plain `{ec['item']}`; the "
            f"lapis is the proof.")
        return None
    agent._note_failure("enchant")
    agent._flush_tail(
        f"{ec['label']}: the option button changed NOTHING -- no lapis was spent, so the "
        f"enchantment did not apply. Almost always experience levels: option {ec['option']} "
        f"needs at least {ec['option']} levels and a table with no bookshelves around it "
        f"only offers low ones. Earn levels first (mining coal, redstone, lapis, diamond "
        f"or quartz, smelting, or killing mobs), then call enchant again. Check [GRID]: "
        f"if the enchanting row still shows item/lapis, take them back with gui_click "
        f"before closing.", "enchant_failed")
    return None


# -- stonecutting -------------------------------------------------------------

def stonecut(cur, info: dict, item: str = "stone", output: str = "",
             button: int = -1, tries: int = 4) -> tuple[list[dict[str, Any]], str]:
    """Cut `item` at the open stonecutter into `output`.

    A quick-move on the result cell is craft-ALL (measured: the handler loops the
    transfer until the input stops producing), so the two paths differ deliberately.
    With `button=N` the whole stack goes in and comes out cut. Searching (`button=-1`)
    loads ONE item per attempt, because a wrong guess would otherwise eat the stack.
    """
    item = str(item)
    output = str(output or "")
    if not _screen_is_open(cur, info):
        return [], ("stonecut: no screen is open -- look_at the stonecutter and "
                    "use_until_gui first.")
    stacks = gui.find_slots(info, item)
    if not stacks:
        return [], f"stonecut: you carry no {item}."
    try:
        button, tries = int(button), max(1, min(12, int(tries)))
    except (TypeError, ValueError):
        return [], f"stonecut: bad button/tries ({button!r}, {tries!r})"
    known = button >= 0
    if known or not output:
        tries = 1
    label = f"stonecut({item})"
    acts: list[dict[str, Any]] = [_gate(label, ("stonecutter",), "stonecutter")]
    if known:
        acts += _quick_move(cur, gui.centre(gui.player_slot_topleft(stacks[0][0])),
                            f"inventory slot {stacks[0][0]} ({item})")
    acts.append(macros.marker("_cutpick", {
        "label": label, "item": item, "output": output, "tried": [],
        "i": max(0, button), "left": tries, "one": not known, "t": 0},
        (70 if not known else 40) * tries + 24))
    return _charge(acts), (f"cutting {item}"
                           + (f" into {output}" if output else "")
                           + (f" with recipe button {button} (the whole stack)" if known
                              else f" -- trying up to {tries} recipe buttons in order, "
                                   f"one item each"))


def _slot_holding(agent, item: str) -> int | None:
    """The player slot holding `item` right now (the frame's own observation)."""
    inv = (agent.ledger._prev or {}).get("inventory") or {}
    for s in range(36):
        if _slot_item({"inventory": inv}, s)[0] == item:
            return s
    return None


@macros.tick("_cutpick")
def _cutpick_tick(agent, cp: dict[str, Any], mk_act):
    """One attempt: (load one item,) click recipe button `i`, take the result, read it."""
    from mcu_worldmodel import procedures as P

    if cp["t"] < 2:
        cp["t"] += 1
        return mk_act()
    i = int(cp["i"])
    if i >= gui.CUT_COLS * gui.CUT_ROWS:
        agent._flush_tail(
            f"{cp['label']}: ran past the last recipe button on the page ({i}). A "
            f"stonecutter only offers the recipes valid for what is in its input cell; "
            f"the [GRID] line says how many buttons are drawn.", "stonecut_no_button")
        return None
    entries: list[dict[str, Any]] = []
    if cp.get("one"):
        src = _slot_holding(agent, cp["item"])
        if src is None:
            agent._flush_tail(
                f"{cp['label']}: no {cp['item']} left in the inventory to try recipe "
                f"button {i} with.", "stonecut_no_input")
            return None
        src_tl = gui.centre(gui.player_slot_topleft(src))
        entries += [P._servo(src_tl, f"inventory slot {src}")]
        entries += P.click("attack", probe=True)
        entries += [P._servo(gui.centre(gui.CUT_IN), "stonecutter input")]
        entries += P.click("use", probe=True)
        entries += [P._servo(src_tl, f"inventory slot {src}")]
        entries += P.click("attack", probe=True)
    entries += [P._servo(gui.cut_button_centre(i), f"stonecutter recipe button {i}")]
    entries += P.click("attack")
    entries += [P.noop() for _ in range(4)]
    entries += [P._servo(gui.centre(gui.CUT_OUT), "stonecutter output")]
    entries += P.click("attack", shift=True, probe=True)
    entries.append(macros.marker("_cutread", {
        "label": cp["label"], "item": cp["item"], "output": cp["output"], "i": i,
        "one": bool(cp.get("one")), "tried": list(cp["tried"]),
        "left": int(cp["left"]) - 1, "base": dict(agent._cur_inv), "t": 0}, 12))
    _splice(agent, entries)
    return None


@macros.tick("_cutread")
def _cutread_tick(agent, cr: dict[str, Any], mk_act):
    """What did that button produce? Stop on a match, otherwise try the next one."""
    base = cr["base"]
    got = {k: v - base.get(k, 0) for k, v in agent._cur_inv.items()
           if v - base.get(k, 0) > 0 and k != cr["item"]}
    if not got and cr["t"] < 18:
        cr["t"] += 1
        return mk_act()
    tried = list(cr["tried"]) + [f"button {cr['i']} -> "
                                 + (", ".join(sorted(got)) if got else "nothing")]
    want = cr["output"]
    hit = bool(got) if not want else (want in got)
    if hit or int(cr["left"]) <= 0:
        _splice(agent, _finish_cut(agent, cr, tried, got, want, hit))
        return None
    _splice(agent, [macros.marker("_cutpick", {
        "label": cr["label"], "item": cr["item"], "output": want, "tried": tried,
        "i": int(cr["i"]) + 1, "left": int(cr["left"]), "one": cr["one"], "t": 0}, 70)])
    return None


def _finish_cut(agent, cr: dict[str, Any], tried: list[str], got: dict[str, int],
                want: str, hit: bool) -> list[dict[str, Any]]:
    """Quick-move whatever is left in the input cell back, then say what happened.

    The stonecutter is NOT in `macros.KEEPS_CONTENTS`: its input is a screen-handler
    inventory, so a stack left there makes every close_inventory a refusal the model
    then has to reason its way out of.
    """
    from mcu_worldmodel import procedures as P

    spent = max(0, _lost(agent).get(cr["item"], 0))
    _writeoff(agent, cr["item"], spent)
    entries = [P._servo(gui.centre(gui.CUT_IN), "stonecutter input")]
    entries += P.click("attack", shift=True, probe=True)
    entries += [P._servo(gui.cursor_park("stonecutter"), "clear of the cells")]
    if hit:
        agent.cursor_stats["stonecut_ok"] = agent.cursor_stats.get("stonecut_ok", 0) + 1
        note = (f"{cr['label']}: "
                f"{', '.join(f'{k} +{v}' for k, v in sorted(got.items()))}. Recipe "
                f"buttons tried: {'; '.join(tried)}.")
        if cr["one"]:
            note += (f" That search cut ONE item per button. Call stonecut(item="
                     f"\"{cr['item']}\", button={cr['i']}) to cut the whole stack in "
                     f"one go.")
    else:
        agent.cursor_stats["stonecut_missed"] = (
            agent.cursor_stats.get("stonecut_missed", 0) + 1)
        agent._note_failure("stonecut")
        note = (f"{cr['label']}: never produced {want or 'anything'}. Buttons tried: "
                f"{'; '.join(tried)}. A stonecutter offers only the recipes valid for "
                f"its input ([GRID] counts the buttons drawn); if none of them is what "
                f"you want, that recipe belongs on a crafting table. Whatever DID come "
                f"out is in your inventory.")
    entries.append(macros.marker("_cutnote", {"note": note, "t": 0}, 10))
    return entries


@macros.tick("_cutnote")
def _cutnote_tick(agent, cn: dict[str, Any], mk_act):
    """Write the stonecut verdict after the input cell has been emptied."""
    if cn["t"] < 8:
        cn["t"] += 1
        return mk_act()
    agent.memory.add_note(cn["note"])
    return None


# -- registration -------------------------------------------------------------

_OPEN_IT = ("The container's screen must already be open: stand within ~4 blocks, "
            "equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand "
            "gets placed instead), look_at the block's exact x/y/z, then use_until_gui.")


def register_all(register, Procedure) -> None:
    register(Procedure(
        "container_take",
        "Empty the open chest, barrel or double chest into your inventory in ONE call: "
        "reads which cells hold something from the frame, quick-moves each of them, and "
        "reports what arrived and how many cells are left. Says so and stops when the "
        "chest is empty or your inventory is full.",
        container_take, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " A chest cell does not say WHAT is in it, only that it "
                                 "is full, so `items` filters the report, not the taking.",
        params={"items": '"all" (default) or a comma-separated list you are looking for',
                "max_stacks": "cells to empty in this call (default 27; a double chest "
                              "has 54, so call it twice)"}))
    register(Procedure(
        "container_put",
        "Move an item from your inventory into the open chest and verify it left your "
        "inventory. n=0 quick-moves every stack you carry; a smaller n puts exactly that "
        "many into one empty cell.",
        container_put, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " A chest keeps its contents across a close.",
        params={"item": "item name from [INV]", "n": "items to move, 0 = all (default)"}))
    register(Procedure(
        "brew",
        "Load the open brewing stand in ONE call: potions/water bottles into the three "
        "bottle cells, blaze powder into the fuel cell, one ingredient into the "
        "ingredient cell, verified against the inventory and the [GRID] row. It does NOT "
        "wait -- a brew takes 400 ticks and runs with the screen closed.",
        brew, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " Fire resistance is two brews: water bottles + "
                                 "nether_wart (-> awkward), then + magma_cream, 400 ticks "
                                 "each. Call brew(bottles=0) for the second one, the "
                                 "bottles are already in the stand.",
        params={"ingredient": "nether_wart, magma_cream, blaze_powder, sugar, "
                              "glistering_melon_slice... (default nether_wart)",
                "bottles": "bottles to load from your inventory, 0-3 (default 3; 0 when "
                           "they are already in the stand)",
                "fuel": "blaze_powder (default) or none"}))
    register(Procedure(
        "brew_take",
        "Take the three bottles out of the open brewing stand and report what arrived. "
        "Every potion reads as `potion` in the inventory -- the harness cannot name which "
        "one, only count them.",
        brew_take, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " Nothing has finished before 400 ticks per ingredient "
                                 "have passed since brew().",
        params={}))
    register(Procedure(
        "enchant",
        "Enchant an item at the open enchanting table in ONE call: the item and your "
        "lapis in, option button 1-3 clicked, the item and the leftover lapis taken back "
        "out. Verified on the lapis spent -- the inventory observation carries no NBT, so "
        "that is the only channel that says the enchantment applied.",
        enchant, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " Option N costs N lapis_lazuli AND N experience levels; "
                                 "with no levels the click does nothing and the macro "
                                 "says so.",
        params={"item": "what to enchant, e.g. diamond_sword (default)",
                "option": "which of the three offers, 1-3 (default 1)"}))
    register(Procedure(
        "stonecut",
        "Cut a block at the open stonecutter into another and take the result. The "
        "recipe buttons are icons the harness cannot read, so it clicks them in order "
        "and reports what each produced until `output` arrives; the note names the "
        "button that worked so the next call can pass it directly.",
        stonecut, needs_cursor=True, needs_info=True,
        preconditions=_OPEN_IT + " Each attempt consumes one input item. A stonecutter "
                                 "offers only the recipes valid for its input; [GRID] "
                                 "counts how many buttons are drawn.",
        params={"item": "what to cut, e.g. stone (default)",
                "output": "what you want out, e.g. stone_bricks (drives the search)",
                "button": "recipe button 0-11 to click directly (default -1 = search). "
                          "Measured for stone: 0 chiseled_stone_bricks, 1 "
                          "stone_brick_slab, 2 stone_brick_stairs, 3 stone_brick_wall",
                "tries": "buttons to try when searching (default 4)"}))
