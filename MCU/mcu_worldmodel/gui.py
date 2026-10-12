"""Exact inventory-GUI geometry, so crafting is arithmetic instead of guesswork.

The engine has no craft command (see craft_env.py), so crafting is performed the way a
human does it: open the inventory, move the mouse over slots, click. Every primitive that
needs is available -- `inventory` toggles the screen, `camera` moves the cursor, `attack`
is left-click, `use` is right-click. What was missing is knowing *where the slots are*.

The numbers below are Minecraft 1.16's `InventoryScreen` / `CraftingScreen` layout in GUI
pixels. They are fixed by the game, not estimated:

    container      176 x 166, centred on the screen
    slot pitch     18 px
    survival 2x2   input slots at (98,18) (116,18) (98,36) (116,36); output at (154,28)
    table 3x3      input slots from (30,17), pitch 18; output at (124,35)
    main inventory 3 rows x 9 cols from (8,84)
    hotbar         one row from (8,142)

Two conversions turn those into actions:

    GUI px -> screen px    `MinecraftSim` forces `guiscale_range=[1,1]`, so 1:1.
    screen px -> degrees   `GUIConstants.MOUSE_MULTIPLIER = 0.1` converts mouse pixels to
                           camera degrees, so one pixel is 0.1 deg and the 18 px slot pitch
                           is 1.8 deg -- which is where `CURSOR_DEG_PER_SLOT` came from,
                           and a live run has now confirmed it by reaching the
                           `crafting_table` milestone with it.

**The cursor's opening position was measured, not assumed.** Two earlier versions of this
module guessed it -- first the screen centre, then a corner reached by over-moving into the
clamp -- and both emitted perfectly-formed crafts that moved nothing at all: no engine
error, planks unchanged, GUI open throughout. A sweep of px-per-degree over a 12x range
failed at every value, which is what finally showed the scale was never the problem.

A calibration scan settles it: put a known stack in slot 0, open the inventory, and walk
the cursor one slot at a time, clicking at each stop, until the stack leaves the slot. Slot 0 (container centre (16, 150)) came back at **(0, +5) slots** from
the opening position, so the cursor opens at container **(16, 60)** -- `CURSOR_OPEN` below.
Repeat the scan if the render size or GUI scale ever changes.

`info['inventory']` is slot-keyed (`{slot: {type, quantity}}`), so a recipe can be compiled
against the *actual* inventory rather than assuming where an ingredient sits. That is what
makes this reliable where a fixed macro is not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# -- geometry -----------------------------------------------------------

CONTAINER_W, CONTAINER_H = 176, 166
SLOT_PITCH = 18
#: MEASURED, not derived. `GUIConstants.MOUSE_MULTIPLIER = 0.1` suggests 10 px per degree,
#: and that value is wrong for cursor motion inside a GUI -- it is the human-play
#: interface's mouse->camera conversion, which is a different direction of travel.
#:
#: Measured by diffing frames (the changed-pixel centroid IS the cursor) while sweeping
#: the cursor right in 6-degree steps: x runs 310 -> 460 across 36
#: degrees, i.e. 4.17 px/deg. Using 10 made every absolute move overshoot by ~2.4x, which
#: is why three well-formed craft macros moved nothing at all.
#:
#: Pairwise estimates are noisy (the centroid includes the highlighted slot under the
#: cursor, which jumps between slots), so this is the endpoint fit over the clean span.
#: Measure again if the render size or GUI scale changes.
PX_PER_DEGREE = 4.17

SURVIVAL_CRAFT_IN = [(98, 18), (116, 18), (98, 36), (116, 36)]
SURVIVAL_CRAFT_OUT = (154, 28)
TABLE_CRAFT_IN = [(30 + 18 * c, 17 + 18 * r) for r in range(3) for c in range(3)]
TABLE_CRAFT_OUT = (124, 35)
#: `AbstractFurnaceScreen` (1.16): smelt input above the flame, fuel below it, result to
#: the right of the arrow. Same 176x166 centred container as the crafting screens, so the
#: player-inventory offsets are shared and only these three slots are new. One run hit
#: this gap live: it reached `furnace` at step 4316 with no addressable furnace slots.
FURNACE_IN = (56, 17)
FURNACE_FUEL = (56, 53)
FURNACE_OUT = (116, 35)
MAIN_INV_ORIGIN = (8, 84)       # slot 9 .. 35, three rows of nine
HOTBAR_ORIGIN = (8, 142)        # slot 0 .. 8


def slot_topleft(slot: int) -> tuple[int, int]:
    """Container-pixel top-left of an `info['inventory']` slot id.

    MineRL numbers slots 0-8 as the hotbar and 9-35 as the three main rows, which is the
    opposite vertical order to how they are drawn -- the hotbar is at the bottom. Getting
    this backwards puts every click one region away, which looks like a calibration error
    and is not.
    """
    if not 0 <= slot <= 35:
        raise ValueError(f"inventory slot out of range: {slot}")
    if slot < 9:
        return (HOTBAR_ORIGIN[0] + SLOT_PITCH * slot, HOTBAR_ORIGIN[1])
    idx = slot - 9
    return (MAIN_INV_ORIGIN[0] + SLOT_PITCH * (idx % 9),
            MAIN_INV_ORIGIN[1] + SLOT_PITCH * (idx // 9))


def centre(topleft: tuple[int, int]) -> tuple[float, float]:
    """Slot boxes are 16 px inside an 18 px pitch; aim at the middle of the box."""
    return (topleft[0] + 8.0, topleft[1] + 8.0)


#: Where the cursor sits, in container coordinates, when the inventory opens. The screen
#: centre -- which frame evidence settled after the sweep calibration had said otherwise:
#: `vision.find_cursor` run over four runs' saved frames finds the arrow at exactly
#: (320, 180) screen = (88, 83) container on freshly-opened screens (one run step 535,
#: one run step 2160, another step 1200). The sweep's (16, 60) was the scale error of
#: its own probe moves folded into the origin. With per-tick anchoring this value only
#: covers the tick or two before the arrow is first measured, but it should still be the
#: right value.
CURSOR_OPEN = (88.0, 83.0)


def container_origin(render_w: int = 640, render_h: int = 360) -> tuple[float, float]:
    """Top-left of the container in SCREEN pixels. The container is centred."""
    return ((render_w - CONTAINER_W) / 2.0, (render_h - CONTAINER_H) / 2.0)


def to_screen(gui_pos: tuple[float, float],
              render: tuple[int, int] = (640, 360)) -> tuple[float, float]:
    """Container coordinates -> screen pixels."""
    ox, oy = container_origin(*render)
    return (ox + gui_pos[0], oy + gui_pos[1])


def cursor_home(render_w: int = 640, render_h: int = 360) -> tuple[float, float]:
    """Container coordinates of the screen centre.

    Kept because it is the documented behaviour of a Minecraft GUI opening, and it is what
    the geometry tests pin. It is deliberately NOT used to seed a CursorPath -- see the
    module docstring for why that produced a craft that moved nothing.
    """
    ox, oy = container_origin(render_w, render_h)
    return (render_w / 2.0 - ox, render_h / 2.0 - oy)


# -- building the action sequence ---------------------------------------

def _noop() -> dict[str, Any]:
    from mcu_worldmodel.procedures import noop
    return noop()


def _press(key: str, ticks: int = 2) -> list[dict[str, Any]]:
    from mcu_worldmodel.procedures import act
    return [act(**{key: 1}) for _ in range(ticks)] + [_noop()]


@dataclass
class CursorPath:
    """Accumulates cursor moves and clicks in SCREEN pixels, tracking the true position.

    Tracking matters because every move is relative: emitting each hop from an assumed
    origin compounds the error, and after four ingredient placements the cursor is in the
    wrong region entirely -- with nothing in the log to say so, because each individual
    camera delta was correct. `home()` establishes the origin by clamping.
    """
    pos: tuple[float, float] = CURSOR_OPEN
    actions: list[dict[str, Any]] = field(default_factory=list)

    def move_to(self, target: tuple[float, float]) -> "CursorPath":
        from mcu_worldmodel import camera as _camera
        from mcu_worldmodel.procedures import act
        dx = (target[0] - self.pos[0]) / PX_PER_DEGREE
        dy = (target[1] - self.pos[1]) / PX_PER_DEGREE
        # Routed through `camera` rather than emitted directly, because whether one tick
        # suffices depends on the encoder in the path. In `env` it does and `split` returns
        # the angle unchanged. Under the `agent` encoder only 11 values per axis survive,
        # an 18px slot asked for as one 4.32-degree move arrived as 3.215 (13.4px), and the
        # old `self.pos = target` recorded it as exact -- four moves later the cursor was a
        # full slot out with nothing in the log to say so. Tracking the sum of what was
        # actually emitted is correct either way.
        xs, ys = _camera.split(dx), _camera.split(dy)
        for pitch, yaw in _camera.plan(dy, dx):
            self.actions.append(act(camera=[pitch, yaw]))
        # Where the cursor actually is, which is not where it was aimed.
        self.pos = (self.pos[0] + sum(xs) * PX_PER_DEGREE,
                    self.pos[1] + sum(ys) * PX_PER_DEGREE)
        return self

    def left_click(self) -> "CursorPath":
        # Release matters: `attack` held across ticks reads as click-and-drag, which
        # distributes a stack across slots instead of picking it up.
        self.actions += _press("attack")
        return self

    def right_click(self) -> "CursorPath":
        self.actions += _press("use")
        return self

    def settle(self, ticks: int = 1) -> "CursorPath":
        self.actions += [_noop() for _ in range(ticks)]
        return self


# -- recipes ------------------------------------------------------------

#: (grid, {cell_index: ingredient}, output_count). `grid` is "2x2" for the survival
#: inventory or "3x3" for a placed crafting table. Cell indices are row-major.
#:
#: Only the recipes the two milestone chains actually need. Ingredients name a *category*
#: where the game accepts any of a set (any plank, any log); `resolve` expands that against
#: the real inventory.
PLANKS = "@planks"
LOGS = "@logs"

RECIPES: dict[str, tuple[str, dict[int, str], int]] = {
    "planks":         ("2x2", {0: LOGS}, 4),
    "stick":          ("2x2", {0: PLANKS, 2: PLANKS}, 4),
    "crafting_table": ("2x2", {0: PLANKS, 1: PLANKS, 2: PLANKS, 3: PLANKS}, 1),
    "wooden_pickaxe": ("3x3", {0: PLANKS, 1: PLANKS, 2: PLANKS,
                               4: "stick", 7: "stick"}, 1),
    "stone_pickaxe":  ("3x3", {0: "cobblestone", 1: "cobblestone", 2: "cobblestone",
                               4: "stick", 7: "stick"}, 1),
    "iron_pickaxe":   ("3x3", {0: "iron_ingot", 1: "iron_ingot", 2: "iron_ingot",
                               4: "stick", 7: "stick"}, 1),
    "diamond_pickaxe": ("3x3", {0: "diamond", 1: "diamond", 2: "diamond",
                                4: "stick", 7: "stick"}, 1),
    "stone_sword":    ("3x3", {1: "cobblestone", 4: "cobblestone", 7: "stick"}, 1),
    "iron_sword":     ("3x3", {1: "iron_ingot", 4: "iron_ingot", 7: "stick"}, 1),
    "diamond_sword":  ("3x3", {1: "diamond", 4: "diamond", 7: "stick"}, 1),
    "furnace":        ("3x3", {0: "cobblestone", 1: "cobblestone", 2: "cobblestone",
                               3: "cobblestone", 5: "cobblestone",
                               6: "cobblestone", 7: "cobblestone", 8: "cobblestone"}, 1),
    "flint_and_steel": ("2x2", {0: "iron_ingot", 1: "flint"}, 1),
    "blaze_powder":   ("2x2", {0: "blaze_rod"}, 2),
    "ender_eye":      ("2x2", {0: "blaze_powder", 1: "ender_pearl"}, 1),
    "torch":          ("2x2", {0: "coal", 2: "stick"}, 4),
    # Nether preparation: a bucket carries the water that turns a lava source into
    # obsidian; charcoal torches need no coal (any log smelted).
    "bucket":         ("3x3", {3: "iron_ingot", 5: "iron_ingot", 7: "iron_ingot"}, 1),
    "charcoal_torch": ("2x2", {0: "charcoal", 2: "stick"}, 4),
}
#: Recipe keys whose product statistic is another name: `charcoal_torch` makes `torch`.
PRODUCT = {"charcoal_torch": "torch"}

# The rest of the vanilla 1.16 recipe book that the task suite's public task texts
# name, or that any survival player reaches for (tools of every tier, containers,
# furniture, ranged gear, food). Public game knowledge, in the same (grid, cells, out)
# shape; a family ingredient ("@planks", "@wool") matches any member. The product's
# statistic name may carry a material prefix ("oak_fence", "white_bed"): macros_gui.
# product_matches accepts the family suffix.
WOOL = "@wool"
_T = {"wooden": PLANKS, "stone": "cobblestone", "iron": "iron_ingot", "golden": "gold_ingot",
      "diamond": "diamond"}
for _tier, _mat in _T.items():
    RECIPES[f"{_tier}_axe"] = ("3x3", {0: _mat, 1: _mat, 3: _mat, 4: "stick", 7: "stick"}, 1)
    RECIPES[f"{_tier}_shovel"] = ("3x3", {1: _mat, 4: "stick", 7: "stick"}, 1)
    RECIPES[f"{_tier}_hoe"] = ("3x3", {0: _mat, 1: _mat, 4: "stick", 7: "stick"}, 1)
    if f"{_tier}_pickaxe" not in RECIPES:
        RECIPES[f"{_tier}_pickaxe"] = ("3x3", {0: _mat, 1: _mat, 2: _mat, 4: "stick",
                                               7: "stick"}, 1)
    if f"{_tier}_sword" not in RECIPES:
        RECIPES[f"{_tier}_sword"] = ("3x3", {1: _mat, 4: _mat, 7: "stick"}, 1)
RECIPES.update({
    "ladder":          ("3x3", {0: "stick", 2: "stick", 3: "stick", 4: "stick", 5: "stick",
                                6: "stick", 8: "stick"}, 3),
    "chest":           ("3x3", {0: PLANKS, 1: PLANKS, 2: PLANKS, 3: PLANKS, 5: PLANKS,
                                6: PLANKS, 7: PLANKS, 8: PLANKS}, 1),
    "door":            ("3x3", {0: PLANKS, 1: PLANKS, 3: PLANKS, 4: PLANKS, 6: PLANKS,
                                7: PLANKS}, 3),
    "fence":           ("3x3", {3: PLANKS, 4: "stick", 5: PLANKS, 6: PLANKS, 7: "stick",
                                8: PLANKS}, 3),
    "fence_gate":      ("3x3", {3: "stick", 4: PLANKS, 5: "stick", 6: "stick", 7: PLANKS,
                                8: "stick"}, 1),
    "boat":            ("3x3", {3: PLANKS, 5: PLANKS, 6: PLANKS, 7: PLANKS, 8: PLANKS}, 1),
    "bookshelf":       ("3x3", {0: PLANKS, 1: PLANKS, 2: PLANKS, 3: "book", 4: "book",
                                5: "book", 6: PLANKS, 7: PLANKS, 8: PLANKS}, 1),
    "bed":             ("3x3", {0: WOOL, 1: WOOL, 2: WOOL, 3: PLANKS, 4: PLANKS, 5: PLANKS}, 1),
    "carpet":          ("2x2", {0: WOOL, 1: WOOL}, 3),
    "glass_pane":      ("3x3", {3: "glass", 4: "glass", 5: "glass", 6: "glass", 7: "glass",
                                8: "glass"}, 16),
    "item_frame":      ("3x3", {0: "stick", 1: "stick", 2: "stick", 3: "stick", 4: "leather",
                                5: "stick", 6: "stick", 7: "stick", 8: "stick"}, 1),
    "painting":        ("3x3", {0: "stick", 1: "stick", 2: "stick", 3: "stick", 4: WOOL,
                                5: "stick", 6: "stick", 7: "stick", 8: "stick"}, 1),
    "stonecutter":     ("3x3", {1: "iron_ingot", 3: "stone", 4: "stone", 5: "stone"}, 1),
    "enchanting_table": ("3x3", {1: "book", 3: "diamond", 4: "obsidian", 5: "diamond",
                                 6: "obsidian", 7: "obsidian", 8: "obsidian"}, 1),
    "clock":           ("3x3", {1: "gold_ingot", 3: "gold_ingot", 4: "redstone",
                                5: "gold_ingot", 7: "gold_ingot"}, 1),
    "compass":         ("3x3", {1: "iron_ingot", 3: "iron_ingot", 4: "redstone",
                                5: "iron_ingot", 7: "iron_ingot"}, 1),
    "diorite":         ("2x2", {0: "quartz", 1: "cobblestone", 2: "cobblestone",
                                3: "quartz"}, 2),
    "cake":            ("3x3", {0: "milk_bucket", 1: "milk_bucket", 2: "milk_bucket",
                                3: "sugar", 4: "egg", 5: "sugar", 6: "wheat", 7: "wheat",
                                8: "wheat"}, 1),
    "bread":           ("3x3", {3: "wheat", 4: "wheat", 5: "wheat"}, 1),
    "sugar":           ("2x2", {0: "sugar_cane"}, 1),
    "paper":           ("3x3", {3: "sugar_cane", 4: "sugar_cane", 5: "sugar_cane"}, 3),
    "book":            ("2x2", {0: "paper", 1: "paper", 2: "paper", 3: "leather"}, 1),
    "shears":          ("2x2", {1: "iron_ingot", 2: "iron_ingot"}, 1),
    "bow":             ("3x3", {1: "stick", 2: "string", 3: "stick", 5: "string", 7: "stick",
                                8: "string"}, 1),
    "arrow":           ("3x3", {1: "flint", 4: "stick", 7: "feather"}, 4),
    "fishing_rod":     ("3x3", {2: "stick", 4: "stick", 5: "string", 6: "stick",
                                8: "string"}, 1),
    "lead":            ("3x3", {0: "string", 1: "string", 3: "string", 4: "slime_ball",
                                8: "string"}, 2),
    "shield":          ("3x3", {0: PLANKS, 1: "iron_ingot", 2: PLANKS, 3: PLANKS, 4: PLANKS,
                                5: PLANKS, 7: PLANKS}, 1),
    "snow_block":      ("2x2", {0: "snowball", 1: "snowball", 2: "snowball", 3: "snowball"}, 1),
    "jack_o_lantern":  ("2x2", {0: "carved_pumpkin", 2: "torch"}, 1),
    "beehive":         ("3x3", {0: PLANKS, 1: PLANKS, 2: PLANKS, 3: "honeycomb",
                                4: "honeycomb", 5: "honeycomb", 6: PLANKS, 7: PLANKS,
                                8: PLANKS}, 1),
    "iron_bars":       ("3x3", {3: "iron_ingot", 4: "iron_ingot", 5: "iron_ingot",
                                6: "iron_ingot", 7: "iron_ingot", 8: "iron_ingot"}, 16),
    "iron_helmet":     ("3x3", {0: "iron_ingot", 1: "iron_ingot", 2: "iron_ingot",
                                3: "iron_ingot", 5: "iron_ingot"}, 1),
    "iron_chestplate": ("3x3", {0: "iron_ingot", 2: "iron_ingot", 3: "iron_ingot",
                                4: "iron_ingot", 5: "iron_ingot", 6: "iron_ingot",
                                7: "iron_ingot", 8: "iron_ingot"}, 1),
    "iron_leggings":   ("3x3", {0: "iron_ingot", 1: "iron_ingot", 2: "iron_ingot",
                                3: "iron_ingot", 5: "iron_ingot", 6: "iron_ingot",
                                8: "iron_ingot"}, 1),
    "iron_boots":      ("3x3", {3: "iron_ingot", 5: "iron_ingot", 6: "iron_ingot",
                                8: "iron_ingot"}, 1),
    "stone_bricks":    ("2x2", {0: "stone", 1: "stone", 2: "stone", 3: "stone"}, 4),
    "smooth_stone_slab": ("3x3", {3: "smooth_stone", 4: "smooth_stone", 5: "smooth_stone"}, 6),
    "cobblestone_slab": ("3x3", {3: "cobblestone", 4: "cobblestone", 5: "cobblestone"}, 6),
    "stone_brick_slab": ("3x3", {3: "stone_bricks", 4: "stone_bricks", 5: "stone_bricks"}, 6),
    "cobblestone_stairs": ("3x3", {0: "cobblestone", 3: "cobblestone", 4: "cobblestone",
                                   6: "cobblestone", 7: "cobblestone", 8: "cobblestone"}, 4),
    "lantern":         ("3x3", {0: "iron_nugget", 1: "iron_nugget", 2: "iron_nugget",
                                3: "iron_nugget", 4: "torch", 5: "iron_nugget",
                                6: "iron_nugget", 7: "iron_nugget", 8: "iron_nugget"}, 1),
    "glass_bottle":    ("3x3", {3: "glass", 5: "glass", 7: "glass"}, 3),
    "brewing_stand":   ("3x3", {1: "blaze_rod", 3: "cobblestone", 4: "cobblestone",
                                5: "cobblestone"}, 1),
    "iron_nugget":     ("2x2", {0: "iron_ingot"}, 9),
    "gold_nugget":     ("2x2", {0: "gold_ingot"}, 9),
    "flower_pot":      ("3x3", {3: "brick", 5: "brick", 7: "brick"}, 1),
    "smoker":          ("3x3", {1: LOGS, 3: LOGS, 4: "furnace", 5: LOGS, 7: LOGS}, 1),
})

_CATEGORY_MEMBERS = {
    PLANKS: ("oak_planks", "birch_planks", "spruce_planks", "jungle_planks",
             "acacia_planks", "dark_oak_planks", "crimson_planks", "warped_planks"),
    LOGS: ("oak_log", "birch_log", "spruce_log", "jungle_log",
           "acacia_log", "dark_oak_log", "stripped_oak_log", "stripped_birch_log",
           "stripped_spruce_log", "crimson_stem", "warped_stem"),
    WOOL: tuple(f"{c}_wool" for c in (
        "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
        "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")),
}


def find_slots(info: dict, ingredient: str) -> list[tuple[int, int]]:
    """[(slot, quantity)] holding `ingredient`, best-stocked first.

    A category ingredient matches any member. Sorting by quantity means a recipe drawing
    four planks takes them from the fullest stack rather than emptying a stack of one and
    then failing on the next cell with the grid half-filled -- which leaves the GUI in a
    state the next turn has to recognise and undo.
    """
    inv = info.get("inventory")
    if not isinstance(inv, dict):
        return []
    wanted = _CATEGORY_MEMBERS.get(ingredient, (ingredient,))
    found = []
    for slot, entry in inv.items():
        if not isinstance(entry, dict):
            continue
        # Empty slots report `type: "none"` in this engine -- not "air", which is what the
        # handler source suggests. Measured on a live reset.
        if entry.get("type") in ("none", "air", None):
            continue
        if entry.get("type") in wanted:
            qty = entry.get("quantity", 0)
            qty = int(qty.item()) if hasattr(qty, "item") else int(qty)
            if qty > 0:
                found.append((int(slot), qty))
    found.sort(key=lambda sq: -sq[1])
    return found


def can_craft(info: dict, item: str) -> tuple[bool, str]:
    """Whether the inventory holds enough for `item`. Returns (ok, why-not).

    Checked before emitting 30-odd ticks of cursor work: a craft attempted without the
    ingredients leaves the grid half-filled and the agent with a screen it has to reason
    its way out of, which is far more expensive than the check.
    """
    spec = RECIPES.get(item)
    if spec is None:
        return False, f"no recipe for {item!r}"
    _, cells, _ = spec
    need: dict[str, int] = {}
    for ing in cells.values():
        need[ing] = need.get(ing, 0) + 1
    for ing, count in need.items():
        have = sum(q for _, q in find_slots(info, ing))
        if have < count:
            return False, f"need {count}x {ing.lstrip('@')}, have {have}"
    return True, ""


def craft_actions(info: dict, item: str, render: tuple[int, int] = (640, 360)
                  ) -> tuple[list[dict[str, Any]], str]:
    """Actions that craft `item` from the current inventory. ([], reason) if it cannot.

    Assumes the correct screen is ALREADY open -- the survival inventory for a 2x2 recipe,
    a crafting table's screen for a 3x3 one -- because opening a table means walking to it
    and right-clicking it, which is navigation, not GUI work, and belongs in the plan the
    agent writes rather than buried inside a macro.

    Ingredients are placed with right-click (one item per press) so a stack is not dumped
    into a single cell, and the output is taken with left-click.
    """
    ok, why = can_craft(info, item)
    if not ok:
        return [], why
    grid, cells, _ = RECIPES[item]
    in_slots = SURVIVAL_CRAFT_IN if grid == "2x2" else TABLE_CRAFT_IN
    out_slot = SURVIVAL_CRAFT_OUT if grid == "2x2" else TABLE_CRAFT_OUT

    # Spend each source stack down as cells consume it, so two cells needing the same
    # ingredient do not both plan to take it from a slot that only had one.
    remaining: dict[str, list[list[int]]] = {}
    for ing in set(cells.values()):
        remaining[ing] = [[s, q] for s, q in find_slots(info, ing)]

    path = CursorPath()
    # One stack at a time: pick it up, right-click one item into each cell it supplies,
    # then put the remainder back. This is the pattern the agent's own successful crafts
    # used -- right-click while holding a stack deposits a single item and keeps holding
    # the rest, so N cells cost N clicks rather than N round trips to the source slot.
    by_source: dict[int, list[int]] = {}
    for cell, ing in sorted(cells.items()):
        if cell >= len(in_slots):
            return [], f"cell {cell} outside the {grid} grid"
        stacks = remaining[ing]
        while stacks and stacks[0][1] <= 0:
            stacks.pop(0)
        if not stacks:
            return [], f"ran out of {ing.lstrip('@')} while filling the grid"
        stacks[0][1] -= 1
        by_source.setdefault(stacks[0][0], []).append(cell)

    for src_slot, target_cells in by_source.items():
        path.move_to(centre(slot_topleft(src_slot))).left_click()
        for cell in target_cells:
            path.move_to(centre(in_slots[cell])).right_click()
        path.move_to(centre(slot_topleft(src_slot))).left_click()

    path.move_to(centre(out_slot)).left_click().settle(2)
    logger.info(f"[gui] craft {item}: {len(path.actions)} ticks")
    return path.actions, ""


def reference() -> str:
    """The recipe list as the prompt shows it."""
    lines = []
    for item, (grid, cells, out) in RECIPES.items():
        ings: dict[str, int] = {}
        for ing in cells.values():
            key = ing.lstrip("@")
            ings[key] = ings.get(key, 0) + 1
        need = ", ".join(f"{n}x {k}" for k, n in ings.items())
        where = "inventory 2x2" if grid == "2x2" else "crafting table 3x3"
        lines.append(f"- `{item}` (x{out}) <- {need}  [{where}]")
    return "\n".join(lines)


# -- containers beyond the crafting table and the furnace ----------------------
#
# Six more screens, all measured from real sim frames (the reference
# JPEGs the probe left behind, cross-checked against Minecraft 1.16's screen handlers).
#
# The one fact that makes all of them addressable: **the container is centred, so a
# screen whose `backgroundHeight` is not 166 is drawn SHIFTED against the fixed 176x166
# frame `container_origin`, `slot_topleft` and `CursorState` work in.** Measured by
# finding the container's top bevel row on the centre column of each frame -- a dark
# row, two near-white rows, then body:
#
#     inventory / table / furnace / brewing / enchanting / stonecutter / anvil
#                                     dark row at y=97  ->  H = 360 - 2*97 = 166
#     chest / barrel                  dark row at y=96  ->  H = 168  (114 + 3*18)
#     double chest                    dark row at y=69  ->  H = 222  (114 + 6*18)
#
# Every constant below is already expressed in the FIXED frame, that shift folded in,
# so `gui.centre(...)` + `procedures.cursor_to_*` address them without knowing about it.
# A 3-row chest's own slot rows are 18+18r in ITS container, which is 17+18r here; its
# player inventory is 85/103/121/143 there, which is exactly the standard 84/102/120/142
# here -- the two-pixel taller texture cancels the one-pixel higher origin. Only the
# double chest actually moves the player rows (to 111/129/147, hotbar 169).

#: `backgroundHeight` per screen kind (vision.screen_kind names).
SCREEN_H = {"inventory": 166, "table": 166, "furnace": 166, "brewing": 166,
            "enchanting": 166, "stonecutter": 166, "anvil": 166,
            "chest": 168, "chest2": 222}
#: Container rows of the chest-shaped screens (chest = chest/barrel/shulker/ender chest).
CHEST_ROWS = {"chest": 3, "chest2": 6}


def screen_shift(kind: str) -> int:
    """Fixed-frame y offset of `kind`'s container: (166 - backgroundHeight) / 2."""
    return (CONTAINER_H - SCREEN_H.get(kind, CONTAINER_H)) // 2


def chest_cells(kind: str = "chest") -> list[tuple[int, int]]:
    """Container-cell top-lefts of a chest screen, row-major (9 per row)."""
    rows = CHEST_ROWS.get(kind, 3)
    off = screen_shift(kind)
    return [(8 + SLOT_PITCH * c, 18 + SLOT_PITCH * r + off)
            for r in range(rows) for c in range(9)]


def player_slot_topleft(slot: int, kind: str | None = None) -> tuple[int, int]:
    """`slot_topleft` for a screen that moves the player inventory.

    `GenericContainerScreenHandler` puts the player rows at 103 + (rows-4)*18 and the
    hotbar at 161 + (rows-4)*18 of ITS container. Folding in `screen_shift` leaves a
    3-row chest on the standard 84/142 and moves only the double chest -- addressing a
    double chest's slots with `slot_topleft` would click 27 px too high, which is a
    different slot, not a near miss.
    """
    rows = CHEST_ROWS.get(kind or "")
    if rows is None:
        return slot_topleft(slot)
    if not 0 <= slot <= 35:
        raise ValueError(f"inventory slot out of range: {slot}")
    off = screen_shift(kind or "") + (rows - 4) * SLOT_PITCH
    if slot < 9:
        return (HOTBAR_ORIGIN[0] + SLOT_PITCH * slot, 161 + off)
    idx = slot - 9
    return (MAIN_INV_ORIGIN[0] + SLOT_PITCH * (idx % 9), 103 + SLOT_PITCH * (idx // 9) + off)


#: `BrewingStandScreenHandler`: fuel (blaze powder) top-left, ingredient above the
#: bottles, three bottle slots in an arc. Confirmed against the sim frame -- all five
#: read as slots (dark top/left bevel, white bottom/right) and (56,17), where a furnace
#: puts its smelt cell, does not.
BREW_FUEL = (17, 17)
BREW_INGREDIENT = (79, 17)
BREW_BOTTLES = [(56, 51), (79, 58), (102, 51)]

#: `EnchantmentScreenHandler`: the item and the lapis slot, and the three enchant
#: buttons. The buttons are NOT slots: each is a 108x19 hit rect, measured on the sim
#: frame as a dark block from container x=60 (left border) to x=167 (right border),
#: rows 14-32, 33-51 and 52-70.
ENCHANT_ITEM = (15, 47)
ENCHANT_LAPIS = (35, 47)
ENCHANT_BUTTONS = [(60, 14), (60, 33), (60, 52)]
ENCHANT_BUTTON_SIZE = (108, 19)


def enchant_button_centre(i: int) -> tuple[float, float]:
    """Where to click enchant option `i` (0-2)."""
    x, y = ENCHANT_BUTTONS[max(0, min(2, int(i)))]
    return (x + ENCHANT_BUTTON_SIZE[0] / 2.0, y + ENCHANT_BUTTON_SIZE[1] / 2.0)


#: `StonecutterScreenHandler`: input left, result right. The result is a BIG slot --
#: its drawn frame is 26x26 at (138,28), the item area is the usual 16x16 at (143,33)
#: (measured: dark border column at x=138, white at x=163, same rows). The furnace's
#: output is drawn the same way at (111,30); both are addressed by their item area.
CUT_IN = (20, 33)
CUT_OUT = (143, 33)
#: The recipe list: a recessed dark panel, measured at container x 52..115 (4 columns
#: of 16) and y 15..68 (3 rows of 18), border at x=51 / y=14, scrollbar to its right.
#: A button is 16x18; buttons fill row-major and only the recipes valid for the input
#: are drawn, so button 0 is always the first available recipe.
CUT_RECIPE_ORIGIN = (52, 15)
CUT_BUTTON_W, CUT_BUTTON_H = 16, 18
CUT_COLS, CUT_ROWS = 4, 3


def cut_button_centre(i: int) -> tuple[float, float]:
    """Where to click stonecutter recipe button `i` (0-11, row-major, 4 per row)."""
    i = max(0, min(CUT_COLS * CUT_ROWS - 1, int(i)))
    return (CUT_RECIPE_ORIGIN[0] + CUT_BUTTON_W * (i % CUT_COLS) + CUT_BUTTON_W / 2.0,
            CUT_RECIPE_ORIGIN[1] + CUT_BUTTON_H * (i // CUT_COLS) + CUT_BUTTON_H / 2.0)


#: `AnvilScreenHandler`: base item, material, result. Recognition only -- no macro is
#: registered for the anvil (renaming needs a text field the action space cannot type in).
ANVIL_IN = (27, 47)
ANVIL_ADD = (76, 47)
ANVIL_OUT = (134, 47)


def cursor_park(kind: str = "inventory") -> tuple[float, float]:
    """A point inside `kind`'s container that is NOT a slot, for parking the pointer.

    The white arrow (and any stack riding it) is drawn over whatever slot it sits on,
    and `vision.slot_occupied` reads texture, so a pointer left on a cell makes that
    cell read FULL: after `container_take` emptied a chest the last cell it clicked
    still reported an item, and the next take clicked at nothing (a staged scene).
    Every container's bottom strip, below the hotbar row and inside the frame, is plain
    body on all nine screens.
    """
    bottom = screen_shift(kind) + SCREEN_H.get(kind, CONTAINER_H) - 1
    return (170.0, float(bottom - 5))
