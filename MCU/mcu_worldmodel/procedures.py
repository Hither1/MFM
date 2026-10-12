"""Procedures: named action macros, and the reason both tasks are reachable at all.

The blocking fact about these two tasks: **`MinecraftSim` does not expose a crafting
action.** `HumanSurvival.create_actionables()` grants keyboard, camera, chat, voxel and
mob handlers only -- the `CraftAction` / `SmeltAction` / `EquipAction` handlers exist in
the tree but are never installed. So `craft_item` cannot be issued; it can only be
*performed*, by opening the inventory GUI and moving a mouse cursor over slots.

That matters because crafting is most of the score. Of the diamond task's 10 milestones,
5 are `craft_item` (crafting_table, wooden_pickaxe, stone_pickaxe, furnace, iron_pickaxe);
of the dragon's 24, 9 are. An agent that cannot craft is capped at roughly the first two
milestones of either task no matter how good its world model is. (The reference agent in
RDI-Foundation/Minecraft-agentbeats emits one flat action dict per step and its prompt
never explains GUI item manipulation, which is the ceiling it runs into.)

So crafting is provided here as *procedures*: parameterised macros over the primitive
action space, which the agent calls by name instead of steering a cursor blind. This is
not a shortcut around the benchmark -- every action a procedure emits is an ordinary
env action that goes through the same `sim.step`, and the milestone still only fires when
MineRL's own `craft_item` statistic moves. It is a skill library, and it is the
`procedures/` box in the architecture: induction can add to it, and a procedure that
stops working is a belief to be revised like any other.

**The calibration below is derived, not measured, and is expected to need fixing.**
`GUIConstants.MOUSE_MULTIPLIER = 0.1` converts mouse pixels to camera degrees in the
human-play interface; assuming the inverse holds inside the env, and that a 1.0 GUI scale
puts Minecraft's standard 18-GUI-pixel slot pitch at 18 screen pixels, one slot is 1.8
degrees of camera. Both halves of that are assumptions about a direction of travel that
was only ever exercised the other way. `calibrate_cursor()` measures it in-sim, and
`CURSOR_DEG_PER_SLOT` is a module-level default that a run overrides from what it learns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

from mcu_worldmodel import camera as _camera

# MEASURED (see gui.PX_PER_DEGREE): the cursor moves ~4.17 px per
# degree inside a GUI, so an 18px slot is ~4.32 degrees -- not the 1.8 that
# MOUSE_MULTIPLIER=0.1 implies. The old value meant `cursor_to(dx=2)` moved slightly under
# one slot, which is why GUI work converged only after many small visual corrections
# (~450 steps for one 2x2 craft in the first run, with sub-slot nudges like dx=0.25 near
# the end). With the right unit the agent's own closed loop should converge far faster.
CURSOR_DEG_PER_SLOT = 4.32

# The inventory GUI's slot grid, in slots relative to the cursor's rest position at the
# centre of the screen when the GUI opens. Minecraft's survival inventory:
#   crafting output   at (+1.5, -2.5) roughly
#   crafting 2x2      two slots up-left of centre
#   main inventory    3 rows of 9, starting ~1 row below centre
#   hotbar            one row below that
# Offsets are held as data so a calibration run can correct them without touching code.
GRID = {
    "craft_out_2x2": (2.0, -2.0),
    "craft_in_2x2": [(-0.5, -2.5), (0.5, -2.5), (-0.5, -1.5), (0.5, -1.5)],
    "craft_out_3x3": (3.0, -1.0),
    "craft_in_3x3": [(-1.0, -2.0), (0.0, -2.0), (1.0, -2.0),
                     (-1.0, -1.0), (0.0, -1.0), (1.0, -1.0),
                     (-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
    "inv_origin": (-4.0, 1.0),      # top-left of the 3x9 main inventory
    "hotbar_origin": (-4.0, 4.0),   # left-most hotbar slot
}


def noop() -> dict[str, Any]:
    """One env action with nothing pressed. The base every macro entry starts from --
    built fresh each call because these go into a list that the runner mutates."""
    a = {k: 0 for k in (
        "attack", "back", "forward", "jump", "left", "right", "sneak", "sprint", "use",
        "inventory", *(f"hotbar.{i}" for i in range(1, 10)),
    )}
    a["camera"] = [0.0, 0.0]
    return a


def act(**kw) -> dict[str, Any]:
    a = noop()
    for k, v in kw.items():
        key = k.replace("hotbar_", "hotbar.")
        if key == "camera":
            a["camera"] = [float(v[0]), float(v[1])]
        else:
            a[key] = int(v)
    return a


def repeat(action: dict[str, Any], n: int) -> list[dict[str, Any]]:
    return [dict(action) for _ in range(max(1, n))]


@dataclass
class Procedure:
    """A named macro. `build` returns the env actions; `preconditions` is prose the
    prompt shows so the agent knows when calling it is pointless (crafting a stone
    pickaxe with no cobblestone burns 30 steps and teaches nothing)."""
    name: str
    doc: str
    build: Callable[..., Any]
    preconditions: str = ""
    params: dict[str, str] = field(default_factory=dict)
    #: True when `build` takes the live `info` first and returns (actions, note).
    needs_info: bool = False
    #: True when `build` takes the harness's `CursorState` first and returns
    #: (actions, note), advancing it as it goes. This is what makes a cursor address
    #: absolute: the move is computed from where the cursor *is*, so the quantisation
    #: residue `camera.split` discards is carried instead of being re-incurred on every
    #: call, and a whole recipe fits in one plan entry.
    needs_cursor: bool = False


# -- GUI primitives ------------------------------------------------------

def cursor_to(dx_slots: float, dy_slots: float, deg_per_slot: float | None = None
              ) -> list[dict[str, Any]]:
    """Move the GUI cursor by a slot offset.

    Composed from the deltas the encoder can actually deliver (`camera.plan`). Equal
    division does not work here: only 11 values per axis survive the round trip, and the
    old `<=8 degree` rule both overshot (8 rounds *up* to 10) and undershot one-slot moves
    by a quarter of a slot, with `CursorPath` recording them as exact either way.
    """
    d = deg_per_slot if deg_per_slot is not None else CURSOR_DEG_PER_SLOT
    yaw_total, pitch_total = dx_slots * d, dy_slots * d
    return [act(camera=[p, y]) for p, y in _camera.plan(pitch_total, yaw_total)]


#: Ticks a servo may spend before giving up. Sized by simulation, not hope: with the
#: damped step in `agent._servo_tick`, the true px/degree swept over 3.3-6.7 against the
#: assumed 4.17, integer-pixel motion, and 15% of frames hiding the arrow, the worst of
#: 8,000 random moves landed in 12 ticks. 16 leaves margin; a real move is 3-6.
SERVO_BUDGET = 16


def _servo(target: tuple[float, float], label: str) -> dict[str, Any]:
    """A closed-loop queue entry: land the cursor on `target`, measured from the frame.

    Expansion used to compute the whole camera sequence here, open loop, from the tracked
    position -- and the tracked position drifts (see vision.py: 60 px measured after one
    long GUI session). The runner resolves this marker one tick at a time against the
    position `vision.find_cursor` measured from the *current* frame, so the error being
    corrected is real, not remembered. The marker is data, not a closure, so a plan is
    still serialisable and the log can say what was asked for.
    """
    return {"_servo": {"tx": float(target[0]), "ty": float(target[1]),
                       "label": label, "budget": SERVO_BUDGET},
            "_cost": SERVO_BUDGET}


def _move_to(cur, target: tuple[float, float]) -> list[dict[str, Any]]:
    """Camera actions taking the cursor from where it is to `target`, in container px.

    `cur` is advanced by each action as it is built, so the position it reports afterwards
    is the sum of what was actually emitted rather than what was asked for. Whether those
    differ depends on the encoder in the path: under `action_type="env"` the camera arrives
    as written and the two agree exactly, while under `MCU_CAMERA_QUANTISED` composing from
    the bin set leaves up to ~0.2 degrees per axis on the table. Tracking the sum is right
    either way, and it is what separates this from `cursor_to` -- a relative helper that
    starts from zero every call re-incurs whatever error there is on every call, and six
    placements into a 3x3 grid was enough to put a click in the wrong cell.
    """
    pitch, yaw = cur.delta_to(target)
    actions = [act(camera=[p, y]) for p, y in _camera.plan(pitch, yaw)]
    for a in actions:
        cur.apply(a)
    return actions


def cursor_to_slot(cur, slot: int = 0) -> tuple[list[dict[str, Any]], str]:
    """Put the cursor on a player inventory slot by its `info['inventory']` id.

    Slots 0-8 are the hotbar and 9-35 the three main rows -- the opposite vertical order
    to how they are drawn. Both screens draw the player inventory at the same container
    offsets, so this address is unambiguous whichever one is open.
    """
    from mcu_worldmodel import gui as _gui

    try:
        slot = int(slot)
        target = _gui.centre(_gui.slot_topleft(slot))
    except (TypeError, ValueError) as e:
        return [], f"cursor_to_slot: {e}"
    # No is_open rejection at parse time: the address is absolute, so nothing about the
    # move depends on the projected state -- and the projection is wrong exactly when it
    # matters (a runtime-refused close leaves the screen open that the projection closed,
    # and the recovery entries after it must still parse). The runner stops a servo with
    # a [NOTE] if no screen is actually open when it runs.
    cur.pos = target
    return [_servo(target, f"slot {slot}")], ""


def cursor_to_cell(cur, grid: str = "3x3", cell: Any = 0
                   ) -> tuple[list[dict[str, Any]], str]:
    """Put the cursor on a crafting cell. `cell` is a row-major index, or "out".

    Unlike a player slot, this address depends on which screen is open -- the survival 2x2
    and a table's 3x3 sit in overlapping container space -- so the caller says which.
    """
    from mcu_worldmodel import gui as _gui

    grid = str(grid)
    if grid not in ("2x2", "3x3", "furnace"):
        return [], f"cursor_to_cell: grid must be '2x2', '3x3' or 'furnace', not {grid!r}"
    # No is_open rejection here either -- see cursor_to_slot.
    if grid == "furnace":
        cells = [_gui.FURNACE_IN, _gui.FURNACE_FUEL]
        out_cell = _gui.FURNACE_OUT
    else:
        cells = _gui.SURVIVAL_CRAFT_IN if grid == "2x2" else _gui.TABLE_CRAFT_IN
        out_cell = _gui.SURVIVAL_CRAFT_OUT if grid == "2x2" else _gui.TABLE_CRAFT_OUT
    if str(cell).lower() in ("out", "output", "result"):
        target = _gui.centre(out_cell)
    else:
        try:
            idx = int(cell)
        except (TypeError, ValueError):
            return [], f"cursor_to_cell: bad cell {cell!r}"
        if not 0 <= idx < len(cells):
            return [], f"cursor_to_cell: {grid} has cells 0-{len(cells) - 1}, not {idx}"
        target = _gui.centre(cells[idx])
    cur.pos = target
    return [_servo(target, f"{grid} cell {cell}")], ""


def cursor_by(cur, dx: float = 0.0, dy: float = 0.0
              ) -> tuple[list[dict[str, Any]], str]:
    """The relative move, kept, but routed through the tracked position.

    Same interface `cursor_to` always had. The difference is that the residue of this move
    is carried into the next one instead of being thrown away, which is what made a run of
    small relative nudges wander off a slot with nothing in the log to say so.
    """
    if not cur.is_open:
        return [], "cursor_to: no screen is open, so there is no cursor to move."
    from mcu_worldmodel import gui as _gui

    here = cur.pos
    target = (here[0] + float(dx) * _gui.SLOT_PITCH,
              here[1] + float(dy) * _gui.SLOT_PITCH)
    return _move_to(cur, target), ""


def open_screen(cur) -> tuple[list[dict[str, Any]], str]:
    """Open the survival inventory, and tell the cursor tracker the screen is up."""
    actions = open_inventory()
    if not cur.is_open:
        cur.opened(cur.current)          # the projection follows the toggle
    return actions, ""


def close_screen(cur, force: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Close the screen. The runner refuses the toggle while items are off-inventory --
    One run dropped four of its five logs to exactly that close and re-chopped for ~700
    steps -- so a close that would drop something becomes a no-op plus a [NOTE], and the
    plan continues. `force=true` closes anyway, for the case where dropping the item is
    actually the intent (it stays on the floor at your feet)."""
    # Measured BEFORE the toggle is applied to the projection -- applying it closes the
    # projected screen and clears the baseline `off_inventory` reads against.
    held = cur.off_inventory(cur.current)
    actions = close_inventory(force=force)
    cur.closed()                         # the projection follows the toggle
    if force:
        return actions, ""
    if held:
        txt = ", ".join(f"{k}x{v}" for k, v in sorted(held.items()))
        return actions, (f"closing with {txt} off-inventory (in the cursor or in a "
                         f"crafting grid); the runner will refuse the toggle unless the "
                         f"items are back in a slot by then. stow_items banks the cursor "
                         f"stack and any [GRID]-occupied craft cells into empty slots. "
                         f"A FURNACE keeps its in/fuel/out contents across a close -- if "
                         f"the missing items sit there, close_inventory with force=true "
                         f"is lossless. force=true otherwise drops them deliberately.")
    return actions, ""


def click(button: str = "attack", hold: int = 2, gui: bool = True,
          probe: bool = False, shift: bool = False) -> list[dict[str, Any]]:
    """A click, then a release, as a marker (see agent._click_tick). The release is not
    optional: `attack` held across consecutive ticks reads as a click-and-drag in the
    GUI, which distributes a stack across slots instead of picking it up.

    A marker rather than plain ticks so the runner can hold it against the screen it
    is about to click: one run step 5367 clicked a slot the cursor had already
    been snapped away from, lifted nothing, and the 25 queued entries after it placed
    an empty hand into every cell of the furnace ring.

    `gui=False` marks a WORLD click (place_block right-clicking the ground): the
    screen-open and pointer checks do not apply, and one run proved they must not -- the
    agent itself filed `mechanism_place_block_guard_failure` after its table
    placements were guard-stopped for having no screen open, which is exactly the
    state a world click wants.

    `probe=True` marks a click that is EXPECTED to move nothing when its source is
    empty (stow_items sweeps cells it cannot see into): the lifted-nothing judgment
    stays quiet for it, because that judgment clears the whole queue and a stow is
    mostly such clicks.

    `shift=True` holds sneak with the button: the GUI's quick-move. Measured in the
    standalone sim: a stack jumps between hotbar and main rows, a chest
    slot empties into the inventory, a craft output crafts everything the grid holds
    and lands in the inventory directly -- nothing rides the cursor afterwards."""
    return [{"_click": {"btn": button, "hold": max(1, int(hold)), "t": 0,
                        "gui": bool(gui), "probe": bool(probe), "shift": bool(shift)},
             "_cost": max(1, int(hold)) + 1}]


def open_inventory() -> list[dict[str, Any]]:
    """Press E until a screen is up (closed loop on isGuiOpen; see
    agent._opengui_tick). The toggle is edge-triggered and a press within a tick or
    two of the last screen change is swallowed, so a single blind press queued a
    whole recipe against a closed screen (a staged scene)."""
    return [{"_opengui": {"attempts": 3, "t": 0}, "_cost": 9}]


def _empty_slots(info: dict[str, Any], k: int) -> list[int]:
    """Up to `k` empty player-slot ids, main rows (9-35) before the hotbar (0-8).

    Same order as the close-refusal note's single-slot hint, for the same reason:
    stowing must never silently displace a selected tool."""
    from mcu_worldmodel.milestones import slot_is_empty

    inv = (info or {}).get("inventory")
    if not isinstance(inv, dict):
        return []
    out: list[int] = []
    for sid in list(range(9, 36)) + list(range(0, 9)):
        if slot_is_empty(inv.get(sid) or inv.get(str(sid))):
            out.append(sid)
            if len(out) >= k:
                break
    return out


def stow_items(cur, info, grid: str = "3x3", cells: Any = None
               ) -> tuple[list[dict[str, Any]], str]:
    """Bank the cursor stack and the named craft cells into empty inventory slots.

    The close guard was working -- nothing dropped -- but the recovery it prescribed
    was five manual entries per stack, and under time pressure the models reached for
    force=true instead: 11-26 deliberate drops per arm in two runs, one of which cost
    the iron pickaxe. This is that recovery as one procedure: deposit whatever
    the cursor holds first (a lift with a full hand would swap, not lift), then lift
    each named cell and deposit it. Every move is the same closed-loop servo + click
    the recipes use; `probe` keeps the lifted-nothing judgment quiet for clicks whose
    source may legitimately be empty.

    The harness cannot see which stacks sit where (MineRL observes only the 36 player
    slots), so the CALLER names the cells from the [GRID] line. Furnace slots are
    refused: a furnace keeps its contents across a close, so stowing them wastes
    ticks at best and interrupts a smelt at worst."""
    cells = (list(cells) if isinstance(cells, (list, tuple))
             else [] if cells is None else [cells])
    grid = str(grid)
    if grid == "furnace":
        return [], ("stow_items: furnace slots do not need stowing -- a furnace KEEPS "
                    "its in/fuel/out contents when the screen closes. Only the cursor "
                    "and crafting-grid cells drop on close.")
    if grid not in ("2x2", "3x3"):
        return [], f"stow_items: grid must be '2x2' or '3x3', not {grid!r}"
    n_cells = 4 if grid == "2x2" else 9
    idxs: list[int] = []
    for c in cells[:9]:
        try:
            i = int(c)
        except (TypeError, ValueError):
            return [], f"stow_items: bad cell {c!r}"
        if not 0 <= i < n_cells:
            return [], f"stow_items: {grid} has cells 0-{n_cells - 1}, not {i}"
        idxs.append(i)
    empties = _empty_slots(info, len(idxs) + 1)
    if not empties:
        return [], ("stow_items: every inventory slot is full -- there is nowhere to "
                    "stow into. Free a slot first, or close_inventory with force=true "
                    "and accept the loss.")
    actions: list[dict[str, Any]] = []
    note = ""
    a, err = cursor_to_slot(cur, empties[0])
    if err:
        return [], err
    actions += a + click("attack", probe=True)
    for n, i in enumerate(idxs):
        if n + 1 >= len(empties):
            note = (f"stow_items: only {len(empties)} empty slot(s) -- stowed the "
                    f"cursor and {n} cell(s), left {len(idxs) - n} for after you free "
                    f"more room.")
            break
        a, err = cursor_to_cell(cur, grid, i)
        if err:
            return [], err
        actions += a + click("attack", probe=True)
        a, err = cursor_to_slot(cur, empties[n + 1])
        if err:
            return [], err
        actions += a + click("attack", probe=True)
    return actions, note


def discard_stack(cur, info, slot: int = 9) -> tuple[list[dict[str, Any]], str]:
    """Throw one whole inventory stack away: open the survival inventory, lift the
    stack from `slot`, close with the drop guard released, step back two blocks.

    This action space has no `drop` key, so the only way to shed junk is the one the
    close guard exists to prevent: a screen closed with a stack in the cursor throws
    it on the floor. Models found that route themselves ("Drop the useless pressure
    plate": lift, close_inventory force=true) but spent five entries on it, and the
    step back matters -- a thrown stack lands two blocks ahead and a player who walks
    on picks it straight back up. One entry, lossless for everything except the named
    slot, and the [INV] delta says what left."""
    try:
        sid = int(slot)
    except (TypeError, ValueError):
        return [], f"discard_stack: bad slot {slot!r}"
    if not 0 <= sid <= 35:
        return [], f"discard_stack: slot must be 0-35, not {sid}"
    inv = (info or {}).get("inventory")
    if isinstance(inv, dict):
        from mcu_worldmodel.milestones import slot_is_empty
        entry = inv.get(sid) or inv.get(str(sid))
        if slot_is_empty(entry):
            return [], f"discard_stack: slot {sid} is already empty -- nothing to throw away"
    actions, _ = open_screen(cur)
    a, err = cursor_to_slot(cur, sid)
    if err:
        return [], err
    actions += a + click("attack")
    a, _ = close_screen(cur, force=True)
    actions += a
    actions += repeat(act(back=1), 10)
    return actions, ""


def collect_drops(ticks: int = 48) -> list[dict[str, Any]]:
    """Sweep the immediate area for floating item drops (see agent._sweep_tick).

    Default sized down from 72 after the first live night: 16-46 empty sweeps per arm,
    each running its full budget, mostly called speculatively with no recent break. The
    sweep pays off within ~half a lap when a drop is actually there -- and since the
    audit (87% of all collect_drops ticks gained nothing) an empty sweep
    stops at the runner's 24-tick cap whatever `ticks` says; the budget only matters
    when items keep arriving."""
    t = max(24, min(240, int(ticks)))
    return [{"_sweep": {"i": 0, "t": t}, "_cost": t}]


def close_inventory(force: bool = False) -> list[dict[str, Any]]:
    """Press E until no screen is open on two observations running (closed loop on
    isGuiOpen; see agent._closegui_tick), every press through the drop guard. `force`
    arms the guard for the whole close, so a swallowed first press is retried, not
    refused."""
    return [{"_closegui": {"attempts": 3, "t": 0, "force": bool(force)}, "_cost": 12}]


def _grid_craft(recipe: list[tuple[int, str]], grid: str, take_out: bool
                ) -> list[dict[str, Any]]:
    """Place items into a crafting grid, then take the result.

    `recipe` is (slot_index_in_grid, source) pairs where source names an inventory slot
    the caller has already located. Kept deliberately mechanical -- the *knowledge* of
    which recipe needs what belongs in the model's own memory, not in Python, so that
    the model can revise it when a craft fails.
    """
    out: list[dict[str, Any]] = []
    cells = GRID["craft_in_2x2"] if grid == "2x2" else GRID["craft_in_3x3"]
    out_cell = GRID["craft_out_2x2"] if grid == "2x2" else GRID["craft_out_3x3"]
    here = (0.0, 0.0)
    for idx, _src in recipe:
        if idx >= len(cells):
            continue
        tgt = cells[idx]
        out += cursor_to(tgt[0] - here[0], tgt[1] - here[1])
        out += click("use")          # right-click drops one item into the cell
        here = tgt
    if take_out:
        out += cursor_to(out_cell[0] - here[0], out_cell[1] - here[1])
        out += click("attack")
    return out


# -- movement / mining procedures ---------------------------------------

def look(pitch: float = 0.0, yaw: float = 0.0) -> list[dict[str, Any]]:
    """Turn by a relative amount, composed from the reachable camera deltas (`camera.plan`).

    Turning and moving are never combined here: a yaw change and `forward` in the same tick
    curve the path into an arc, which is the single most common reason a long traverse ends
    up back where it started."""
    return [act(camera=[p, y]) for p, y in _camera.plan(pitch, yaw)] or [noop()]


def look_abs(pitch: float | None = None, yaw: float | None = None,
             ticks: int = 40) -> list[dict[str, Any]]:
    """Steer to an ABSOLUTE orientation, closed-loop against [STATE] every tick.

    `look` turns BY an amount and is only right when the starting pose is known at
    plan time. This marker reads the measured pitch/yaw as it runs, so "aim 38 below
    the horizon" means the same thing from any starting pose. `None` leaves that axis
    alone. Resolved by `WorldModelAgent._lookabs_tick`.
    """
    la: dict[str, Any] = {"remaining": max(1, int(ticks))}
    la["pitch"] = None if pitch is None else max(-90.0, min(90.0, float(pitch)))
    la["yaw"] = None if yaw is None else float(yaw)
    return [{"_lookabs": la, "_cost": max(1, int(ticks))}]


def aim_at_ore(ticks: int = 40) -> list[dict[str, Any]]:
    """Vision-servo the crosshair onto the iron-ore speckle cluster on screen.

    Pairs with the ore sentinel: a mining macro stops with a [NOTE] naming a screen
    pixel; this marker re-detects the cluster every tick and steers until centred.
    Resolved by `WorldModelAgent._aimore_tick`. Follow with a short `mine_forward`."""
    return [{"_aimore": {"remaining": max(1, int(ticks)), "miss": 0},
             "_cost": max(1, int(ticks))}]


def aim_at_tree(ticks: int = 40) -> list[dict[str, Any]]:
    """Vision-servo the crosshair onto the most trunk-like bark column in view.

    The wood-phase mirror of `aim_at_ore`: the trunk detector (colour ratios + tall
    narrow column + green context, calibrated on 268 archived frames) re-runs every
    tick and the camera steers until centred. Resolved by
    `WorldModelAgent._aimtree_tick`. Follow with `chop_tree`; walk forward first if
    the tree is far."""
    return [{"_aimtree": {"remaining": max(1, int(ticks)), "miss": 0},
             "_cost": max(1, int(ticks))}]


def harvest_tree(logs: int = 3, n: int = 500) -> list[dict[str, Any]]:
    """The whole wood loop as one closed-loop macro (see mcu_worldmodel.harvest):
    centre the trunk in view, walk at it until it blocks you, chop until the stat
    stream says a log broke, sweep the drop, repeat until `logs` logs are in the
    inventory or `n` ticks are spent. Resolved by `WorldModelAgent._harvest_tick`."""
    from mcu_worldmodel import harvest

    st = harvest.new_state(int(logs), int(n))
    return [{"_harvest": st, "_cost": st["budget"]}]


def look_at(info: dict[str, Any], x: float = 0.0, y: float = 0.0, z: float = 0.0
            ) -> tuple[list[dict[str, Any]], str]:
    """Aim the crosshair at a world coordinate, computed from ground truth.

    [STATE]'s position and facing are exact, so pointing at a *known place* is
    trigonometry, not estimation -- the same move that took one run fifteen failed
    right-clicks and eight misplaced blocks when done by eye (steps 4434-5927, aiming
    for the table it had itself placed). Convention check against live data: spawn
    (-3009.5, 71, -5572.5) to the first trunk (-3008.7, 73, -5569.6) computes yaw -15,
    which is the heading the agent measured for that exact route.

    Pass the point to aim at; a block's centre is its corner + 0.5 on each axis. Aims
    from the eye (feet + 1.62).
    """
    import math

    from mcu_worldmodel.milestones import location

    pos = location(info)
    if not pos:
        return [], "look_at: no position in the current observation"
    dx = float(x) - pos["x"]
    dy = float(y) - (pos["y"] + 1.62)
    dz = float(z) - pos["z"]
    horiz = math.hypot(dx, dz)
    if horiz < 1e-6 and abs(dy) < 1e-6:
        return [noop()], ""
    # A cell straight overhead or underfoot has no heading of its own: the yaw from a
    # few centimetres of offset is noise, and turning to it swings the crosshair off a
    # block the pitch alone reaches. Keep the heading, move the pitch.
    yaw_target = math.degrees(math.atan2(-dx, dz)) if horiz >= 0.3 else pos["yaw"]
    pitch_target = math.degrees(-math.atan2(dy, horiz)) if horiz > 1e-6 else (
        90.0 if dy < 0 else -90.0)
    dyaw = ((yaw_target - pos["yaw"] + 180.0) % 360.0) - 180.0
    dpitch = max(-90.0, min(90.0, pitch_target)) - pos["pitch"]
    return [act(camera=[p, yw]) for p, yw in _camera.plan(dpitch, dyaw)] or [noop()], ""


def use_until_gui(n: int = 6, item: Any = None) -> list[dict[str, Any]]:
    """Right-click until a screen actually opens, checking the game each attempt.

    `item` names a table/furnace this run placed with place_and_open: the runner aims
    at the remembered spot first (see agent._use_gui_tick), so re-opening it is one
    call instead of a guessed look_at.

    Opening a placed table/furnace by eye was one run's whole endgame: fifteen `use`
    presses that opened nothing, each costing a plan round trip to discover. The runner
    presses, waits two ticks for the screen to come up, reads `isGuiOpen`, and stops the
    moment it is true -- or after `n` presses plus a 20-tick wait for the game to report
    a late screen, with a [NOTE] that the aim (or the held item: a placeable block places
    instead of opening) is the thing to fix."""
    ug: dict[str, Any] = {"attempts": max(1, int(n)), "t": 0}
    if item:
        ug["item"] = str(item)
    return [{"_use_gui": ug, "_cost": 3 * max(1, int(n)) + 20 + (12 if item else 0)}]


def travel(n: int = 40, sprint: bool = True) -> list[dict[str, Any]]:
    """Straight-line travel. Jump is held with forward so a one-block rise does not
    silently stop the traverse -- `moved=0.00` for 40 ticks is the signature."""
    return repeat(act(forward=1, sprint=1 if sprint else 0, jump=1), n)


def go_to(x: float = 0.0, z: float = 0.0, within: float = 1.5, n: int = 120,
          sneak: bool = False) -> list[dict[str, Any]]:
    """Walk to a world coordinate, correcting the heading against [STATE] each tick.

    `travel` walks the direction you happened to be facing; terrain deflects it and the
    error is only visible a model turn later. Every run has paid for that -- one run's map
    covered a 3x7 block box after 1,900 steps of trying to reach trees it could see.
    This closes the loop the same way the GUI servo does: the position is ground truth,
    so the heading to a *known place* is arithmetic, re-done every tick. Stops within
    `within` blocks (horizontal), or after `n` ticks with a [NOTE] saying where it
    actually got to -- repeated no-progress ticks mean a wall or a drop, and the runner
    says so rather than walking into it for the rest of the budget."""
    gt = {"x": float(x), "z": float(z), "within": max(0.5, float(within)),
          "remaining": max(1, int(n)), "stuck": 0, "last": None}
    if sneak in (True, 1, "true", "True", "1"):
        gt["sneak"] = True
    return [{"_goto": gt, "_cost": max(1, int(n))}]


def _mine_seq(steps: list[dict[str, Any]], ore_watch: bool) -> list[dict[str, Any]]:
    """Wrap a mining sequence in a marker so the runner can watch the walls go by.

    Long macros were where ore hid in plain sight: a 200-tick strip mine attaches ONE
    frame, at the end, and every wall face in between went unread (one run spent its
    last 1,100 steps mining past walls nobody looked at). The runner samples the frame
    every few ticks against the iron-ore speckle signature (vision.find_iron_ore;
    recalibration on the live corpus: 5 residual fires over 1,118 frames)
    and stops the macro with a [NOTE] naming the screen position when it sees a
    candidate.
    """
    return [{"_seq": {"steps": steps, "i": 0, "ore": bool(ore_watch)},
             "_cost": len(steps)}]


def mine_ahead(n: int = 120, ore_watch: bool = False) -> list[dict[str, Any]]:
    """Hold attack on exactly what the crosshair is on -- no re-aiming, no walking.

    The extraction half of the ore protocol: aim_at_ore centres the crosshair, and this
    digs out that block without the displacement cycle's pitch changes destroying the
    aim. ore_watch defaults off (you are already on the sighting)."""
    out = _mine_seq(repeat(act(attack=1), n), ore_watch)
    out[0]["_seq"]["label"] = "mine_ahead"
    return out


def _mine_cycle(budget: int, ore_watch: bool, p_lo: float, p_hi: float,
                jump: bool, down_by: float | None, label: str) -> list[dict[str, Any]]:
    """A displacement-verified mining entry (see agent._mfwd_tick).

    The old macros' failure was measured, not hypothetical: 58-97% of mining entries
    across the frozen batch ended with <0.5 blocks of movement (mine_forward held
    attack at one aim forever; strip_mine's 6 attack ticks per step cannot break stone
    at ~18 ticks/block, so it walked into an unbroken wall). Both endgame models
    re-derived the foot-row/eye-row/walk-in cycle in text; this builds it into the
    entry itself and reports "broke N, advanced X" so a stall is visible immediately.
    """
    return [{"_mfwd": {"budget": max(1, int(budget)), "ore": bool(ore_watch),
                       "p_lo": p_lo, "p_hi": p_hi, "jump": jump,
                       "down_by": down_by, "label": label,
                       "phase": "foot", "phase_t": 0, "base_breaks": None,
                       "start": None, "adv_from": None,
                       "broken": 0, "advanced": 0.0, "stall": 0, "used": 0},
             "_cost": max(1, int(budget))}]


def mine_forward(n: int = 60, ore_watch: bool = True) -> list[dict[str, Any]]:
    return _mine_cycle(n, ore_watch, 35.0, 8.0, True, None, "mine_forward")


def dig_down(n: int = 40, until_y: float | None = None) -> list[dict[str, Any]]:
    """Straight down. Cheap and effective for reaching ore depth, and the way most
    from-scratch runs die -- so the procedural doc warns about lava, and the runner
    surfaces the y coordinate every step.

    `until_y` makes the depth the target instead of the tick count: the runner stops the
    moment [STATE] y reaches it. One run planned its descent in fixed 160-tick slices
    and spent its last 1,700 steps strip-mining at y=51 because deeper was another model
    turn away; "dig to y=20" is one entry."""
    dig = [{"_dig": {"remaining": max(1, int(n)),
                     "until_y": None if until_y is None else float(until_y)},
            "_cost": max(1, int(n))}]
    # Absolute aim: the relative look(pitch=60) entry made the landing angle
    # previous_pose + 60 -- from the horizon that is a 60-degree ray into the block
    # diagonally ahead, and 9 of 11 logged digs succeeded or failed purely on the
    # leftover pitch (one run's record dig entered at 22 and won the 82-degree coin;
    # another's entered at 22 and carved a wall for 390 ticks). Same lesson
    # _lookabs_tick already records for stair_down (one run).
    return look_abs(pitch=88) + dig


def stair_down(depth: int = 20, ore_watch: bool = True) -> list[dict[str, Any]]:
    """Descend on a walkable staircase: two blocks out, one step down, repeat.

    The safe descent. `dig_down` bores a vertical shaft, and one run died in its own
    twice -- once reaching y=16 (the run's whole purpose) and once jumping back in to
    recover the dropped items. A staircase cannot be fallen down, can be walked back up
    unaided, and exposes three faces per step to the ore watcher instead of one.
    Roughly 32 ticks per block of depth with a stone pickaxe.
    """
    # The cycle's steeper pitches carve the step down; walking in without a jump drops
    # onto it. The old fixed script (18 attack ticks for TWO blocks when one stone
    # block alone needs ~18) broke at most the first block per step and degenerated.
    return _mine_cycle(int(depth) * 32 + 40, ore_watch, 48.0, 22.0, False,
                       float(depth), "stair_down")


def strip_mine(length: int = 80, ore_watch: bool = True) -> list[dict[str, Any]]:
    """Level tunnel: mine, step, repeat. Diamonds are y=5-12, so this is meant to be run
    after dig_down has reached depth, not at the surface."""
    return _mine_cycle(length, ore_watch, 35.0, 8.0, True, None, "strip_mine")


def chop_tree(n: int = 80, until_logs: int = 1) -> list[dict[str, Any]]:
    """Hold attack on a trunk, stopping as soon as wood actually lands in the inventory.

    The blind version of this is where one run spent 70% of its tick budget: 1,415 attack
    ticks for five logs, because a chop aimed at sky or leaves runs its full duration with
    nothing to say so until the [INV] line at the end. The runner resolves this marker one
    tick at a time and stops the moment the inventory gains `until_logs` items whose name
    contains "log" -- so a well-aimed chop costs what the block costs (~60 ticks by hand)
    and a mis-aimed one still ends at `n`, exactly as before. `until_logs=0` restores the
    fixed-duration behaviour."""
    return [{"_chop": {"remaining": max(1, int(n)), "until": max(0, int(until_logs))},
             "_cost": max(1, int(n))}]


def place_block(pitch_down: float = 45.0) -> list[dict[str, Any]]:
    # A world click: it right-clicks the ground with no screen open, so it must not
    # pass through the GUI-click guards.
    return look(pitch=pitch_down) + click("use", hold=1, gui=False)


def equip_hotbar(slot: int) -> list[dict[str, Any]]:
    slot = max(1, min(9, int(slot)))
    return [act(**{f"hotbar_{slot}": 1}), noop()]


def _craft(info: dict[str, Any], item: str = "crafting_table"
           ) -> tuple[list[dict[str, Any]], str]:
    """Craft `item` from the inventory actually held, using exact GUI geometry.

    The screen must already be open -- the survival inventory for a 2x2 recipe, a crafting
    table's screen for a 3x3 one. Opening a table is navigation (walk to it, right-click
    it), which belongs in the agent's plan rather than hidden inside a macro that would
    silently fail when the table is out of reach.
    """
    from mcu_worldmodel import gui

    actions, why = gui.craft_actions(info, str(item))
    if not actions:
        return [], f"cannot craft {item}: {why}"
    grid = gui.RECIPES[str(item)][0]
    screen = ("the survival inventory (press `inventory`)" if grid == "2x2"
              else "a crafting table's screen (right-click a placed table)")
    return actions, f"crafting {item} via {grid} grid -- requires {screen} to be open"


#: Closed-loop markers whose tick budget can be cut to fit a plan's step cap, and the
#: key that holds it. One run asked for dig_down(n=390, until_y=12) five times: the
#: aim entry (40 ticks) plus the dig (390) exceeded the 400-tick cap, so the dig was
#: DROPPED and only the aim ran -- "changing nothing" five turns in a row -- until the
#: model dug straight down with mine_ahead instead and fell into a cave.
_SHRINKABLE = {"_dig": "remaining", "_chop": "remaining", "_aimore": "remaining",
               "_aimtree": "remaining", "_goto": "remaining", "_lookabs": "remaining",
               "_sweep": "t", "_harvest": "budget", "_mfwd": "budget"}
SHRINK_MIN = 20


def shrink_marker(step: dict[str, Any], fit: int) -> dict[str, Any] | None:
    """A copy of a closed-loop marker with its tick budget cut to `fit`, or None
    when the entry is not a marker, cannot be shrunk, or `fit` is too small to be
    worth running."""
    if fit < SHRINK_MIN:
        return None
    # A marker's own floor (`_min`): under it the macro cannot do its job at all, so the
    # parser drops it whole ("NOT STARTED ... put it first next turn") instead of
    # handing the runner a stub. find_lava shrunk to 112-242 ticks on the tails of
    # 400-tick plans "NOT STARTED" at run time, one model turn each (one run);
    # mine_obsidian shrunk to 74-102 ticks swung at a block that takes 190 (one run).
    if fit < int(step.get("_min", 0) or 0):
        return None
    if "_seq" in step and isinstance(step["_seq"], dict):
        # A mining sequence (stair_down, mine_ahead) is a list of per-tick actions:
        # keep the first `fit` of them.
        out = dict(step)
        inner = dict(step["_seq"])
        inner["steps"] = list(inner.get("steps", []))[:int(fit)]
        out["_seq"] = inner
        out["_cost"] = len(inner["steps"])
        return out if out["_cost"] >= SHRINK_MIN else None
    from mcu_worldmodel import macros as _macros
    for kind, key in {**_SHRINKABLE, **_macros.SHRINK}.items():
        if kind in step and isinstance(step[kind], dict) and key in step[kind]:
            out = dict(step)
            inner = dict(step[kind])
            inner[key] = int(fit)
            out[kind] = inner
            out["_cost"] = int(fit)
            return out
    return None


# -- the registry --------------------------------------------------------

REGISTRY: dict[str, Procedure] = {}
#: Inventory-/screen-aware macros whose parse-time refusal may be undone by the entries
#: BEFORE them in the same plan (a harvest puts logs in the inventory, use_until_gui
#: opens the table): when one of these is refused and is not the plan's first entry, the
#: parser queues a `_later` marker that expands it at run time instead of dropping it
#: (see actions.parse_actions and macros_gui._later_tick). Measured across
#: 7 live arms: 56 of 76 "need Nx" refusals were of this kind, one model turn each.
DEFERRABLE = {"craft", "furnace_load", "furnace_take", "place_and_open"}
#: Procedures whose expansion is a run of independently resumable steps -- a placed
#: block stays placed and the next call skips it -- so the parser may cut them at the
#: step cap and keep the prefix instead of dropping them whole (see actions.parse_actions).
RESUMABLE = {"build_portal_frame"}


def register(p: Procedure) -> None:
    REGISTRY[p.name] = p


#: `atoms`: the procedure set a run
#: shows and expands when the model is to build the rest itself (mcu_worldmodel/own.py).
#: The primitives that carry a measured mechanic the model cannot redo from raw keys in
#: one turn -- the closed-loop aims and walks, the GUI cursor and the one-call craft (9
#: of the dragon's 24 milestones are crafts; the raw-cursor craft cost ~450 steps), the
#: placements, the bucket -- and nothing task-shaped: no tree, no strip mine, no shaft,
#: no obsidian, no portal, no Nether or End macro.
ATOMS = ("look", "look_at", "look_abs", "equip_hotbar", "open_inventory", "close_inventory",
         "cursor_to_slot", "cursor_to_cell", "gui_click", "gui_right_click", "craft",
         "place_and_open", "furnace_load", "furnace_take", "place_at", "use_at", "use_held",
         "go_to", "watch", "mine_ahead", "collect_drops", "fill_bucket", "pillar_up", "eat",
         "throw", "drop_and_pickup", "stow_items", "discard_stack")
#: None = every registered procedure; a set = the names the contract shows and `expand`
#: accepts (the rest answer with a note, never silently).
VISIBLE: set[str] | None = None
#: Whether the arm keeps procedures of its own (`own`): the notes about the atom set
#: offer that way out only where it exists.
OWN: bool = True


def set_visible(names, own: bool = True) -> None:
    global VISIBLE, OWN
    VISIBLE = None if names is None else set(names)
    OWN = bool(own)


def visible():
    return [p for n, p in REGISTRY.items() if VISIBLE is None or n in VISIBLE]


for _p in [
    Procedure("look", "Turn the camera by a relative (pitch, yaw) in degrees, in safe "
              "increments.", lambda pitch=0.0, yaw=0.0: look(pitch, yaw),
              params={"pitch": "degrees, + is down", "yaw": "degrees, + is right"}),
    Procedure("look_at", "Aim the crosshair at a WORLD coordinate (exact, from [STATE] "
              "ground truth). Use for a block whose position you know: your placed "
              "table, a logged ore, a waypoint.",
              look_at, needs_info=True,
              preconditions="A block's centre is corner + 0.5 per axis.",
              params={"x": "world x", "y": "world y", "z": "world z"}),
    Procedure("look_abs", "Steer the camera to an ABSOLUTE pitch/yaw, closed-loop "
              "against [STATE] every tick (works from any starting pose; `look` is "
              "relative). Use look_at for a world point instead.",
              lambda pitch=None, yaw=None, ticks=40: look_abs(pitch, yaw, ticks),
              params={"pitch": "target pitch in degrees (+down, -up), or null to keep",
                      "yaw": "target yaw in degrees, or null to keep",
                      "ticks": "tick budget (default 40)"}),
    Procedure("aim_at_ore", "Steer the crosshair onto the iron- or diamond-ore speckles the "
              "sentinel just flagged (closed loop on the live frame; stops centred or "
              "after 6 undetected frames). Follow with mine_ahead(n=120).",
              lambda ticks=40: aim_at_ore(ticks),
              preconditions="Use right after an ore-stop [NOTE]; the speckles must "
                            "still be on screen.",
              params={"ticks": "tick budget (default 40)"}),
    Procedure("aim_at_tree", "Steer the crosshair onto the most trunk-like bark column "
              "in view (closed loop on the live frame; stops centred or after 6 "
              "undetected frames). Follow with chop_tree; if chops then miss, walk "
              "2-3 blocks forward while centred and chop again.",
              lambda ticks=40: aim_at_tree(ticks),
              preconditions="A daylight scene with a tree (or its leaves) in view; "
                            "useless underground and with a GUI open. It aims at the "
                            "lower, choppable part of the trunk.",
              params={"ticks": "tick budget (default 40)"}),
    Procedure("use_until_gui", "Right-click until a screen opens (checks the game each "
              "press). THE way to open a placed table or furnace; with item=\"crafting_"
              "table\" (or \"furnace\") it first aims at where place_and_open put it.",
              lambda n=6, item=None: use_until_gui(n, item),
              preconditions="Aim at the block first (look_at), or pass item= for one this "
                            "run placed. Select a NON-placeable hotbar item first (your "
                            "pickaxe) -- right-click with a block in hand places the "
                            "block instead of opening.",
              params={"n": "max presses",
                      "item": "crafting_table / furnace placed earlier by place_and_open: "
                              "the runner aims at it for you"}),
    Procedure("go_to", "Walk to a WORLD (x, z), re-aiming against [STATE] every tick "
              "until within reach. Use for any place whose coordinates you know: a "
              "tree you logged, your table, your shaft.",
              lambda x=0.0, z=0.0, within=1.5, n=120, sneak=False: go_to(x, z, within, n, sneak),
              preconditions="Horizontal only -- it walks and hops but will not dig or "
                            "climb more than a block.",
              params={"x": "world x", "z": "world z",
                      "within": "stop distance in blocks (default 1.5)",
                      "n": "max ticks",
                      "sneak": "true: walk holding sneak -- about a third of the speed, "
                               "no hop, and the game does not let a sneaking avatar "
                               "step off a block edge, so the walk stops at a drop "
                               "instead of going over it (default false)"}),
    Procedure("travel", "Run forward in a straight line for n ticks (sprint + jump).",
              lambda n=40, sprint=True: travel(n, sprint),
              preconditions="Aim first with `look`; this does not turn. Prefer go_to "
                            "when you know the destination's coordinates.",
              params={"n": "ticks, 1-200", "sprint": "true/false"}),
    Procedure("harvest_tree", "The wood loop, closed: centre the trunk in view, walk at "
              "it until it blocks you, chop until a log actually breaks, sweep the "
              "drop, repeat until `logs` logs are in the inventory. Breaks leaves in "
              "the way, jumps steps, and ends with a [NOTE] summary (logs collected / "
              "broken, empty chops). Use this for wood instead of aim_at_tree + "
              "chop_tree + walking by hand.",
              lambda logs=3, n=500: harvest_tree(logs, n),
              preconditions="A trunk (bark) must be on screen -- if the [NOTE] says no "
                            "trunk was detected, walk toward visible LEAVES first, then "
                            "run it again. Needs an empty hand or any tool; no screen "
                            "open.",
              params={"logs": "logs to collect (default 3; 4 covers the wooden phase)",
                      "n": "tick budget, 60-1500 (default 500)"}),
    Procedure("chop_tree", "Hold attack on the block you are aiming at (a trunk). Stops "
              "the moment wood breaks -- and also stops EARLY on a miss: after two "
              "non-wood breaks (you are on leaves) or 75 ticks of nothing breaking "
              "(out of reach / sky), with a [NOTE] saying which.",
              lambda n=80, until_logs=1: chop_tree(n, until_logs),
              preconditions="Get within ~3 blocks of the trunk and centre a bark face "
                            "(zoom the frame centre to verify: ./tools/zoom.py <frame> "
                            "288 148 64 64). A miss-note means re-aim or approach, "
                            "never just chop longer.",
              params={"n": "max ticks", "until_logs": "stop after this much wood "
                      "(0 = never stop early)"}),
    Procedure("mine_forward", "Tunnel forward with verified movement: break the foot "
              "block, the eye block, walk into the opening, repeat. Ends with a [NOTE] "
              "reporting blocks broken and blocks ADVANCED; stops early (with a "
              "diagnosis) if it breaks blocks without gaining ground, and with a [NOTE] "
              "if iron- or diamond-ore-like speckles appear.",
              lambda n=60, ore_watch=True: mine_forward(n, ore_watch),
              preconditions="Face the yaw you want the tunnel to run; the cycle sets "
                            "its own pitch. To dig out ONE aimed block (after "
                            "aim_at_ore), use mine_ahead instead.",
              params={"n": "ticks", "ore_watch": "false to ignore ore sightings"}),
    Procedure("mine_ahead", "Hold attack on exactly what the crosshair is on -- no "
              "re-aiming, no walking. It digs out the aimed block without touching "
              "the camera.",
              lambda n=120, ore_watch=False: mine_ahead(n, ore_watch),
              preconditions="Aim first (look_at / look_abs).",
              params={"n": "max ticks", "ore_watch": "true to re-enable sightings"}),
    Procedure("dig_down", "Aim straight down and mine the column under your feet, "
              "stopping at a target depth. The descent that has actually reached ore "
              "depth in every run that got there -- give it until_y and commit: 'dig "
              "to y=30' is one entry. The hazard is what opens below your feet (lava, "
              "caves, worst under y~40): watch the frames and the y readout, and stop "
              "at the first lava light.",
              lambda n=40, until_y=None: dig_down(n, until_y),
              preconditions="Never with lava below; check the y coordinate in [STATE].",
              params={"n": "max ticks", "until_y": "stop once y <= this (12 is the "
                      "mine level); omit for a fixed-tick dig"}),
    Procedure("stair_down", "Descend on a walkable staircase. No fall risk and a "
              "walkable way back up, but slow (~32 ticks per block) and it abandons "
              "entries on ground that will not take a stair -- the return trip and "
              "lava-shy stretches are its jobs; for reaching ore depth, dig_down with "
              "until_y is what has worked. Verifies its own descent and reports blocks "
              "broken / advanced / descended in a [NOTE].",
              lambda depth=20, ore_watch=True: stair_down(depth, ore_watch),
              preconditions="~32 ticks per block of depth. Sets its own pitch; face "
                            "the yaw you want the staircase to run.",
              params={"depth": "blocks to descend",
                      "ore_watch": "false to ignore ore sightings"}),
    Procedure("strip_mine", "Level tunnel with verified movement (same cycle as "
              "mine_forward). Ends with a broke/advanced [NOTE]; stops early with a "
              "diagnosis if it digs in place, and with a [NOTE] on an ore sighting.",
              lambda length=80, ore_watch=True: strip_mine(length, ore_watch),
              preconditions="Run it at the mine level (y 11-12, after the one "
                            "descent), torches in the hotbar; face the yaw you want.",
              params={"length": "approx ticks",
                      "ore_watch": "false to ignore ore sightings"}),
    Procedure("place_block", "Look down and right-click to place the held block.",
              lambda pitch_down=45.0: place_block(pitch_down),
              preconditions="Select the block in the hotbar first with equip_hotbar."),
    Procedure("equip_hotbar", "Select hotbar slot 1-9.",
              lambda slot=1: equip_hotbar(slot), params={"slot": "1-9"}),
    Procedure("open_inventory", "Press E to open the inventory GUI.", open_screen,
              needs_cursor=True),
    Procedure("close_inventory", "Press E to close the screen.", close_screen,
              preconditions="Refused (becomes a no-op + [NOTE]) while anything is "
                            "off-inventory -- put it back in a slot first. [CURSOR] "
                            "says what is off-inventory.",
              needs_cursor=True,
              params={"force": "true to close anyway and drop what the cursor holds"}),
    Procedure("stow_items",
              "Bank the cursor stack and the named craft cells into empty inventory "
              "slots (deposits the cursor first, then lifts each cell and banks it), "
              "so the screen can close without dropping anything.",
              stow_items, needs_cursor=True, needs_info=True,
              preconditions="A screen must be open. Name the occupied cells from "
                            "[GRID]. Furnace slots never need this -- a furnace keeps "
                            "its in/fuel/out contents when the screen closes.",
              params={"grid": "2x2 or 3x3 -- which craft grid the open screen has",
                      "cells": "occupied cell indices to clear, e.g. [0, 4]"}),
    Procedure("discard_stack",
              "Throw a whole inventory stack away (there is no drop key): opens the "
              "inventory, lifts the stack in `slot`, force-closes so it lands on the "
              "floor, and steps back so you do not pick it up again. Use it to shed "
              "junk (dirt, gravel, granite/diorite/andesite, surplus cobblestone) when "
              "the Inventory line's free-slot count is low -- a full inventory silently "
              "loses every drop, including ore.",
              discard_stack, needs_cursor=True, needs_info=True,
              preconditions="No screen open; the slot id from [INV]/Hotbar (0-8 hotbar, "
                            "9-35 main rows). Ends facing the same way, two blocks back.",
              params={"slot": "0-35"}),
    Procedure("collect_drops",
              "Walk a small out-and-back sweep to pick up floating item drops; stops "
              "the moment the inventory count rises, and says so either way.",
              lambda ticks=72: collect_drops(ticks),
              preconditions="Use it right after a break, at the spot that broke -- "
                            "pickup needs you within ~1 block, and a sweep with no "
                            "recent break nearby just spends its ticks. Drops can sit "
                            "down the hole or behind the trunk.",
              params={"ticks": "sweep budget, 24-240 (default 48)"}),
    Procedure("cursor_to_slot",
              "Land the cursor ON a player inventory slot, by its [INV] slot id. "
              "Closed loop: steered against the pointer measured in each frame until it "
              "arrives.",
              cursor_to_slot, needs_cursor=True,
              preconditions="A screen must be open. 0-8 is the hotbar, 9-35 the three "
                            "main rows.",
              params={"slot": "0-35"}),
    Procedure("cursor_to_cell",
              "Land the cursor ON a crafting or furnace cell (or the output). Closed "
              "loop, like cursor_to_slot.",
              cursor_to_cell, needs_cursor=True,
              preconditions="The named grid's screen must be the one that is open.",
              params={"grid": "2x2, 3x3 or furnace", "cell": "row-major index (furnace: "
                      "0=smelt input, 1=fuel), or \"out\""}),
    Procedure("cursor_to", "Move the GUI cursor BY a slot offset. Relative -- use "
              "cursor_to_slot / cursor_to_cell when you know where you want to be.",
              cursor_by, needs_cursor=True,
              preconditions="Only meaningful while a screen is open.",
              params={"dx": "slots right", "dy": "slots down"}),
    Procedure("gui_click", "Left-click at the cursor (pick up / place a stack).",
              lambda: click("attack")),
    Procedure("gui_right_click", "Right-click at the cursor (place one item).",
              lambda: click("use")),
    # The open-loop `craft` of 2026-08 (a fixed 34-tick camera sequence) is gone: it
    # moved nothing in the live engine because the cursor's true scale and origin were
    # unknown. The measured cursor changed that -- `_servo` lands on a slot against the
    # pointer found in each frame -- and the one-call crafting macros in macros_gui.py
    # are that closed loop composed: the same servo + click entries the models were
    # hand-writing (57-72% of every landed plan's entries), emitted by the harness from
    # the real inventory, verified against the craft_item statistic.
]:
    register(_p)

from mcu_worldmodel import macros_gui as _macros_gui  # noqa: E402  (registers procedures)
from mcu_worldmodel import macros_world as _macros_world  # noqa: E402
from mcu_worldmodel import macros_nether as _macros_nether  # noqa: E402
from mcu_worldmodel import macros_container as _macros_container  # noqa: E402
from mcu_worldmodel import macros_entity as _macros_entity  # noqa: E402
from mcu_worldmodel import macros_end as _macros_end  # noqa: E402

_macros_gui.register_all(register, Procedure)
_macros_world.register_all(register, Procedure)
_macros_nether.register_all(register, Procedure)
_macros_container.register_all(register, Procedure)
_macros_entity.register_all(register, Procedure)
_macros_end.register_all(register, Procedure)


def expand(name: str, info: dict[str, Any] | None = None, cursor: Any = None,
           **kwargs) -> tuple[list[dict[str, Any]], str]:
    """Turn a procedure call into env actions. Returns (actions, note).

    `info` is the live observation, passed to any procedure whose `needs_info` is set so
    it can compile against the slots the player actually holds. Nothing sets it today:
    `craft` was the one such procedure and it is deliberately unregistered (see the
    registry), so the branch exists for the next inventory-aware macro rather than for a
    caller that is live now.

    `cursor` is the harness's `CursorState` -- in practice a *projection* of it, advanced
    entry by entry as a plan is parsed while the real one is advanced tick by tick as the
    plan executes. Both see the same deltas, so they agree; keeping them separate is what
    stops one move being counted twice. A cursor-aware procedure called without one gets a
    fresh closed state, which refuses the move and says why, rather than silently emitting
    camera deltas computed from an imaginary position.

    An unknown name or bad arguments cost the turn a [NOTE], never an exception -- a
    procedure the model invented should not crash a 12,000-step episode.
    """
    proc = REGISTRY.get(name)
    if proc is not None and VISIBLE is not None and name not in VISIBLE:
        return [], (f"{name!r} is not in this run's procedure set (the atoms): compose it "
                    f"from the atoms and raw actions"
                    + (", or write it as your own procedure under mine/procedures/"
                       if OWN else ""))
    if proc is None:
        logger.warning(f"[procedures] unknown procedure {name!r}")
        return [], f"unknown procedure {name!r}"
    try:
        if proc.needs_cursor:
            if cursor is None:
                from mcu_worldmodel.cursor import CursorState
                cursor = CursorState()
            if proc.needs_info:
                return proc.build(cursor, info or {}, **kwargs)
            return proc.build(cursor, **kwargs)
        if proc.needs_info:
            return proc.build(info or {}, **kwargs)
        return proc.build(**kwargs), ""
    except TypeError as e:
        logger.warning(f"[procedures] bad arguments for {name!r}: {e}")
        return [], f"bad arguments for {name!r}: {e}"


def index() -> str:
    """The procedure list as an index: name, arguments, the first sentence of the doc.
    `--thin` puts this in the contract and the full `reference()` in
    references/procedures.md."""
    lines = []
    for p in visible():
        args = ", ".join(f"{k}=<{v}>" for k, v in p.params.items())
        first = p.doc.split(". ")[0].rstrip(".").strip()
        lines.append(f"- `{p.name}({args})` -- {first}.")
    return "\n".join(lines)


def reference() -> str:
    """The procedure list as the prompt shows it."""
    lines = []
    for p in visible():
        args = ", ".join(f"{k}=<{v}>" for k, v in p.params.items())
        lines.append(f"- `{p.name}({args})` -- {p.doc}"
                     + (f"  [{p.preconditions}]" if p.preconditions else ""))
    return "\n".join(lines)


def calibrate_cursor(step_fn, deg_candidates=(1.2, 1.8, 2.4, 3.0)) -> float:
    """Measure degrees-per-slot in-sim instead of trusting the derivation.

    `step_fn(actions) -> info` runs actions and returns the resulting info. The signal is
    `isGuiOpen` plus whether a known pickup/place round-trip changed the inventory: the
    candidate that moves an item is the right scale. Returns the best candidate, or the
    module default if none worked -- in which case GUI crafting is not going to function
    and the run should say so rather than spend 12,000 steps failing quietly.
    """
    for cand in deg_candidates:
        try:
            info = step_fn(open_inventory() + cursor_to(0, 1, cand) + click("attack")
                           + cursor_to(0, -1, cand) + click("attack") + close_inventory())
            if info and not info.get("isGuiOpen", False):
                logger.info(f"[procedures] cursor calibration candidate {cand} ran clean")
                return cand
        except Exception as e:      # a calibration probe must never kill the episode
            logger.warning(f"[procedures] calibration probe {cand} failed: {e}")
    logger.error("[procedures] cursor calibration found nothing; GUI crafting is "
                 "unlikely to work this run")
    return CURSOR_DEG_PER_SLOT
