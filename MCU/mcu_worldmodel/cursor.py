"""Where the GUI cursor is, held by the harness instead of by the agent.

This module exists because of a measured failure mode. Across seven runs the agent's
belief graph filled with nodes like `state_cursor_step2368_plank_correction` -- 208 of
243 hypotheses in the 12,000-step world-model run were one-shot `state_*` bookkeeping of
this kind. That is not the agent misusing its belief store. `procedures.cursor_to` is
purely *relative* and the harness kept no cursor state at all, so the only place the agent
could record "the cursor is currently a quarter-slot left of the top-left recipe cell" and
be sure of reading it back was the hypothesis graph -- the one channel the prompt renders
every turn.

Holding the position here removes the need for those nodes, and it removes the reason the
agent's plans were two entries long. With a relative-only cursor, every move has to be
followed by a look, and the only way to look is to end the plan and spend a model turn; the
median plan was 2 entries and one stone pickaxe cost 2,950 steps. With an absolute address
(`cursor_to_slot(12)`) a whole recipe is expressible as one plan entry, because each move
is computed from where the cursor actually is rather than from where the last move was
aimed.

**What is exact here and what is not.** The position is exact in the sense that matters:
every camera delta the runner issues is known, and the tracked position is the sum of what
was emitted rather than what was aimed at. Under `action_type="env"` the game applies the
angle as written and the two are the same number; under `MCU_CAMERA_QUANTISED` they are
not, and the residual `cursor_to` used to discard on every call is carried instead. The
addressing is exact in the first regime and bounded in the second, which is the property
absolute addressing needs. What is *not* tracked is the stack the cursor
holds -- MineRL's `inventory` observation covers the 36 player slots and nothing else, so
an item in the cursor and an item sitting in a crafting grid are indistinguishable from
outside. Rather than model clicks and be confidently wrong, `off_inventory` reports the
difference against the inventory as it was when the screen opened and says plainly that it
cannot separate the two. That number is what the agent never had: closing a screen with
items off-inventory is what dropped materials on the floor and made a reopened table "empty
except for two cobblestone".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcu_worldmodel import gui as G

#: Player-inventory slots are drawn at the same container offsets in the survival screen
#: and in a crafting table's screen, so a hit there is unambiguous. The crafting area is
#: not -- the 2x2 and the 3x3 occupy overlapping container space -- and `over()` says so
#: rather than picking one.
_RENDER = (640, 360)


def _bounds(render: tuple[int, int] = _RENDER) -> tuple[float, float, float, float]:
    """Container-coordinate bounds of the screen: (min_x, min_y, max_x, max_y).

    The cursor clamps at the window edge, not at the container edge, and the container is
    smaller than the window -- so the reachable range is negative on both axes. Clamping to
    the container instead would make the harness believe a move landed short when the game
    had actually let it through.
    """
    ox, oy = G.container_origin(*render)
    return (-ox, -oy, render[0] - ox, render[1] - oy)


@dataclass
class CursorState:
    """The GUI cursor, in container pixels. `pos is None` means no screen is open."""

    pos: tuple[float, float] | None = None
    #: `inventory_counts` as it was when the screen opened; the baseline `off_inventory`
    #: is measured against. None while no screen is open.
    baseline: dict[str, int] | None = None
    current: dict[str, int] = field(default_factory=dict)
    render: tuple[int, int] = _RENDER
    #: Step at which `anchor` last overwrote the position with a frame measurement.
    #: -1 = never; a servo will not declare arrival on a position that is pure dead
    #: reckoning unless measurement has been unavailable for several ticks running.
    anchored_step: int = -1

    # -- lifecycle --------------------------------------------------------

    def copy(self) -> "CursorState":
        """A detached projection, for advancing through a plan at planning time.

        The real state is advanced tick by tick as actions execute; the projection is
        advanced entry by entry as they are parsed. They see the same deltas and converge,
        and keeping them separate is what stops a move being counted twice.
        """
        return CursorState(pos=self.pos, baseline=dict(self.baseline)
                           if self.baseline is not None else None,
                           current=dict(self.current), render=self.render)

    def opened(self, inventory: dict[str, int] | None = None) -> None:
        self.pos = G.CURSOR_OPEN
        self.baseline = dict(inventory or {})
        self.current = dict(inventory or {})

    def closed(self) -> None:
        self.pos = None
        self.baseline = None

    @property
    def is_open(self) -> bool:
        return self.pos is not None

    # -- motion -----------------------------------------------------------

    def apply(self, action: dict[str, Any], toggle: bool = True) -> None:
        """Advance by one executed (or planned) env action.

        `toggle` says whether an `inventory` key should open or close the screen here, and
        the two callers want opposite answers. A *projection* being advanced through a plan
        has no observations, so it must follow the toggle or a plan that opens the
        inventory and then addresses a slot would compute that address from a closed state.
        The *real* cursor must not: `isGuiOpen` is the authority for it (a screen can also
        open by right-clicking a table, and close on its own), and following the toggle as
        well double-counts -- the state ends up closed while the game says open, which
        silently discards the inventory baseline `off_inventory` is measured against.
        """
        if action.get("inventory"):
            if not toggle:
                return
            if self.is_open:
                self.closed()
            else:
                self.opened(self.current)
            return
        if self.pos is None:
            return
        cam = action.get("camera") or (0.0, 0.0)
        try:
            pitch, yaw = float(cam[0]), float(cam[1])
        except (TypeError, ValueError, IndexError):
            return
        if not pitch and not yaw:
            return
        lo_x, lo_y, hi_x, hi_y = _bounds(self.render)
        self.pos = (
            min(hi_x, max(lo_x, self.pos[0] + yaw * G.PX_PER_DEGREE)),
            min(hi_y, max(lo_y, self.pos[1] + pitch * G.PX_PER_DEGREE)),
        )

    def delta_to(self, target: tuple[float, float]) -> tuple[float, float]:
        """Degrees (pitch, yaw) that would take the cursor from here to `target`."""
        here = self.pos if self.pos is not None else G.CURSOR_OPEN
        return ((target[1] - here[1]) / G.PX_PER_DEGREE,
                (target[0] - here[0]) / G.PX_PER_DEGREE)

    def anchor(self, measured: tuple[float, float], step: int = 0) -> float:
        """Overwrite the dead-reckoned position with one measured from the frame.

        Returns the drift that was just corrected, in px. Dead reckoning stays useful
        between anchors (the arrow is not drawn on every frame -- transition ticks around
        open/close render the screen without it), but wherever a measurement exists it
        wins: the sum of emitted deltas has unbounded error (integer-pixel motion in the
        game, an endpoint-fit scale constant) and the measurement has none.
        """
        drift = 0.0
        if self.pos is not None:
            drift = ((measured[0] - self.pos[0]) ** 2
                     + (measured[1] - self.pos[1]) ** 2) ** 0.5
        self.pos = (float(measured[0]), float(measured[1]))
        self.anchored_step = step
        return drift

    # -- what the cursor is over ------------------------------------------

    def over(self, screen: str | None = None) -> str:
        """A description of the slot under the cursor, or why there is none.

        Slot boxes are 16 px inside an 18 px pitch, so a position in the 2 px gutter is
        genuinely over nothing and is reported that way. A click there does nothing, and
        an agent told it was "over slot 12" would read the resulting no-op as a broken
        click rather than as a miss it can correct.
        """
        if self.pos is None:
            return "no screen open"
        hits = []
        for slot in range(36):
            if _inside(self.pos, G.slot_topleft(slot)):
                where = "hotbar" if slot < 9 else "inventory"
                hits.append(f"{where} slot {slot}")
                break
        for i, tl in enumerate(G.SURVIVAL_CRAFT_IN):
            if _inside(self.pos, tl):
                hits.append(f"2x2 cell {i} (survival screen)")
        if _inside(self.pos, G.SURVIVAL_CRAFT_OUT):
            hits.append("2x2 output (survival screen)")
        for i, tl in enumerate(G.TABLE_CRAFT_IN):
            if _inside(self.pos, tl):
                hits.append(f"3x3 cell {i} (table screen)")
        if _inside(self.pos, G.TABLE_CRAFT_OUT):
            hits.append("3x3 output (table screen)")
        for name, tl in (("furnace input", G.FURNACE_IN), ("furnace fuel", G.FURNACE_FUEL),
                         ("furnace output", G.FURNACE_OUT)):
            if _inside(self.pos, tl):
                hits.append(f"{name} (furnace screen)")
        hits += self._container_hits(hits)
        if screen is not None and screen in self.SCREEN_OF_TAG.values():
            hits = self._for_screen(hits, screen)
        if not hits:
            return "no slot (between slots, or outside the container)"
        return " / ".join(hits)

    #: `over()` tag -> the vision.screen_kind it belongs to. A hit with no tag
    #: ("hotbar slot 1") is read off the standard player rows, which every screen
    #: draws at the same offset EXCEPT a double chest, whose rows sit 27 px lower.
    SCREEN_OF_TAG = {
        "(survival screen)": "inventory", "(table screen)": "table",
        "(furnace screen)": "furnace", "(chest screen)": "chest",
        "(double chest screen)": "chest2", "(brewing screen)": "brewing",
        "(enchanting screen)": "enchanting", "(stonecutter screen)": "stonecutter",
        "(anvil screen)": "anvil",
    }

    @classmethod
    def _for_screen(cls, hits: list[str], screen: str) -> list[str]:
        """Only the readings that can be true on the screen that is actually open."""
        kept = []
        for hit in hits:
            tag = next((t for t in cls.SCREEN_OF_TAG if t in hit), None)
            if tag is None:
                if screen != "chest2":
                    kept.append(hit)
            elif cls.SCREEN_OF_TAG[tag] == screen:
                kept.append(hit)
        return kept

    def _container_hits(self, hits: list[str]) -> list[str]:
        """`over()` names for the container screens beyond the table and the furnace.

        Reported positionally, like the 2x2/3x3/furnace rows above: the cursor is a
        point and the harness does not pass the open screen in here, so every screen
        whose geometry the point falls in is listed with its own tag and the model
        reads the one it opened. Chest cells are called "cell", never "slot N" --
        `agent._judge_pending_click` reads a "slot <n>" in this string as a PLAYER
        slot id and looks its pixels up with `gui.slot_topleft`, which is the wrong
        geometry for a container cell.
        """
        out: list[str] = []
        for kind, tag in (("chest", "chest screen"), ("chest2", "double chest screen")):
            for i, tl in enumerate(G.chest_cells(kind)):
                if _inside(self.pos, tl):
                    out.append(f"chest cell {i} ({tag})")
                    break
        # A double chest pushes the player rows 27 px down; the loop above this one
        # reads them at the standard offset and would say nothing here.
        for slot in range(36):
            if _inside(self.pos, G.player_slot_topleft(slot, "chest2")):
                where = "hotbar" if slot < 9 else "inventory"
                out.append(f"{where} slot {slot} (double chest screen)")
                break
        for name, tl in (("brewing fuel", G.BREW_FUEL),
                         ("brewing ingredient", G.BREW_INGREDIENT)):
            if _inside(self.pos, tl):
                out.append(f"{name} (brewing screen)")
        for i, tl in enumerate(G.BREW_BOTTLES):
            if _inside(self.pos, tl):
                out.append(f"brewing bottle {i} (brewing screen)")
        for name, tl in (("enchant item", G.ENCHANT_ITEM),
                         ("enchant lapis", G.ENCHANT_LAPIS)):
            if _inside(self.pos, tl):
                out.append(f"{name} (enchanting screen)")
        for name, tl in (("stonecutter input", G.CUT_IN),
                         ("stonecutter output", G.CUT_OUT)):
            if _inside(self.pos, tl):
                out.append(f"{name} (stonecutter screen)")
        for name, tl in (("anvil base", G.ANVIL_IN), ("anvil material", G.ANVIL_ADD),
                         ("anvil result", G.ANVIL_OUT)):
            if _inside(self.pos, tl):
                out.append(f"{name} (anvil screen)")
        # The enchant options (108x19) and the stonecutter's recipe panel (64x54) are
        # big rectangles that overlap most of the other screens' cells; naming them
        # whenever a 16px cell already matched would put five alternatives on the
        # [CURSOR] line for every click. They are reported only when nothing more
        # specific is under the pointer -- which is where a macro aims them.
        if hits or out:
            return out
        for i, (bx, by) in enumerate(G.ENCHANT_BUTTONS):
            if (bx <= self.pos[0] < bx + G.ENCHANT_BUTTON_SIZE[0]
                    and by <= self.pos[1] < by + G.ENCHANT_BUTTON_SIZE[1]):
                out.append(f"enchant option {i + 1} (enchanting screen)")
        rx, ry = G.CUT_RECIPE_ORIGIN
        if (rx <= self.pos[0] < rx + G.CUT_BUTTON_W * G.CUT_COLS
                and ry <= self.pos[1] < ry + G.CUT_BUTTON_H * G.CUT_ROWS):
            i = (int((self.pos[1] - ry) // G.CUT_BUTTON_H) * G.CUT_COLS
                 + int((self.pos[0] - rx) // G.CUT_BUTTON_W))
            out.append(f"stonecutter recipe button {i} (stonecutter screen)")
        return out

    # -- the off-inventory count ------------------------------------------

    def off_inventory(self, inventory: dict[str, int]) -> dict[str, int]:
        """Items that have left the player inventory since the screen opened.

        They are in the cursor's hand or in a crafting grid; from outside the game those
        two are the same observation, so this does not claim to tell them apart. What it
        does tell you is that they are not somewhere safe, which is the fact that decides
        whether closing the screen is free or costs you the ingredients.
        """
        self.current = dict(inventory)
        if self.baseline is None:
            return {}
        out = {}
        for item, was in self.baseline.items():
            gone = was - inventory.get(item, 0)
            if gone > 0:
                out[item] = gone
        return out

    def crafted(self, item: str, count: int) -> dict[str, int]:
        """A craft output landed: its ingredients left the grid for good, so they
        come off the baseline (else they read as "off-inventory" until the screen
        closes -- one run step 3172: one log became four planks and every close for
        the next 200 steps was refused over a log that no longer existed). Returns
        what was written off. Recipes with a wildcard ingredient ('@planks', '@logs')
        write off whichever matching baseline item still has a count."""
        if self.baseline is None:
            return {}
        recipe = G.RECIPES.get(item)
        if recipe is None:
            # The statistic names the product (`oak_planks`); the recipe table names
            # the family (`planks`). Without this the logs a planks craft consumed
            # stayed on the baseline and every later close was refused over them.
            key = next((k for k in G.RECIPES if item.endswith("_" + k)), None)
            recipe = G.RECIPES.get(key) if key else None
        if recipe is None:
            return {}
        # Two recipes can make the same product (torch from coal or from charcoal);
        # the statistic names the product, so pick the variant with MORE of its plain
        # ingredients on the baseline (most-of, not all-of: sticks made in the same
        # session are not on it) -- writing off coal that was never there left the
        # charcoal "off-inventory" and every close refused (audit passes 10-11).
        def _present(rc) -> int:
            return sum(1 for ing in set(rc[1].values())
                       if not ing.startswith("@") and self.baseline.get(ing, 0) > 0)
        for alt, product in G.PRODUCT.items():
            if product == item and alt in G.RECIPES and _present(G.RECIPES[alt]) > _present(recipe):
                recipe = G.RECIPES[alt]
        _, cells, out = recipe
        ops = max(1, int(round(count / max(1, out))))
        need: dict[str, int] = {}
        for ing in cells.values():
            need[ing] = need.get(ing, 0) + ops
        written: dict[str, int] = {}
        for ing, n in need.items():
            if ing.startswith("@"):
                key = ing[1:]
                names = [k for k in self.baseline if key.rstrip("s") in k and self.baseline[k] > 0]
            else:
                names = [ing] if self.baseline.get(ing, 0) > 0 else []
            for name in names:
                take = min(n, self.baseline[name])
                if take <= 0:
                    continue
                self.baseline[name] -= take
                written[name] = written.get(name, 0) + take
                n -= take
                if n <= 0:
                    break
        return written

    # -- rendering --------------------------------------------------------

    def line(self, inventory: dict[str, int] | None = None,
             screen: str | None = None) -> str:
        """The `[CURSOR]` line for the turn prompt.

        `screen` is what `vision.screen_kind` read off the frame. Given it, the line
        names only the readings that screen can produce: without it a point in the
        player rows is reported under every layout at once ("hotbar slot 1 /
        inventory slot 28 (double chest screen)"), and in the from-scratch tasks --
        which never open a container -- three of the four readings on every GUI turn
        are for screens that are not there.
        """
        if self.pos is None:
            return "[CURSOR] no screen open"
        held = self.off_inventory(inventory or self.current)
        held_txt = (", ".join(f"{k}x{v}" for k, v in sorted(held.items()))
                    if held else "nothing")
        return (f"[CURSOR] container=({self.pos[0]:.1f}, {self.pos[1]:.1f})px  "
                f"over={self.over(screen)}  "
                f"off-inventory (in the cursor or in a crafting grid): {held_txt}")


def _inside(pos: tuple[float, float], topleft: tuple[float, float],
            box: int = 16) -> bool:
    return (topleft[0] <= pos[0] < topleft[0] + box
            and topleft[1] <= pos[1] < topleft[1] + box)
