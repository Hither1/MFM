"""The contract and the action reference the four arms read.

The contract (`act_prompt`) is written once per life as AGENTS.md / CLAUDE.md. What the
arms share -- the action schema, the procedure reference, the recipes, the survival and
chain knowledge -- is defined once and is the same string for every arm; the only lines
that differ are the ones that name a memory surface, each a parameter with one value
per `memory_mode`, so a diff of those tables is the protocol difference.
"""
from __future__ import annotations

import re

from mcu_worldmodel import gui as G
from mcu_worldmodel import procedures as P

#: `atoms`: the procedure example in the action reference names an atom.
_DIG_EXAMPLE = '{"procedure": "dig_down", "args": {"n": 40}}'
_ATOM_EXAMPLE = '{"procedure": "mine_ahead", "args": {"n": 100}}'

ACTION_REFERENCE = """\
Each entry in {actions_channel} is either a raw action held for N ticks:

    {{"action": {{"forward": 1, "sprint": 1}}, "repeat": 30}}

or a named procedure, which expands to many ticks:

    {{"procedure": "dig_down", "args": {{"n": 40}}}}

A list of at most {entry_cap} entries, totalling at most {step_cap} environment ticks.

**Raw action keys** (omitted keys default to 0, so specify only what you want):
- "attack": break blocks / hit entities. One tick breaks nothing -- a log takes ~60-100.
- "use": place a block, interact, use the held item.
- "forward" / "back", "left" / "right": "left"/"right" STRAFE, they do not turn you.
- "jump", "sneak", "sprint" (sprint only helps with forward).
- "inventory": toggle the inventory GUI.
- "hotbar.1".."hotbar.9": select a slot (at most one).
- "camera": [pitch_delta, yaw_delta] in degrees. **RELATIVE to where you are looking
  now**, not an absolute target -- repeating the same turn keeps rotating further. Pitch
  clamps at [-90 (straight up), 90 (straight down)]. Trust the pitch in [STATE] over your
  visual read.

This action space has NO "ESC", "drop", "pickItem" or "swapHands". Entries using them are
dropped and you are told so in a [NOTE]. To throw a stack away use the `discard_stack`
procedure (below); it is the one way to shed junk here.

**Procedures** (prefer these -- they handle the fiddly parts and cover many ticks):
{procedures}

**Crafting is ONE call.** This engine has no craft command, so a recipe is performed the
way a human does it -- a screen, a cursor, clicks -- and the harness does that for you:
- `craft(item=..., count=1)` lays out the whole recipe from your REAL inventory (lifts
  each ingredient stack, right-clicks one item into every cell, puts the remainder back,
  takes the output, banks it -- tools go to the hotbar) and VERIFIES it on the
  `craft_item` statistic: its [NOTE] reads "+1 stone_pickaxe crafted ... hotbar 3" or
  says why nothing happened. The RIGHT screen must be open first: `open_inventory` for a
  2x2 recipe, a crafting table's screen for a 3x3 one. Several crafts fit one plan --
  `open_inventory, craft(planks, count=2), craft(stick), craft(crafting_table),
  close_inventory` is the whole wooden phase once the logs are in.
- `place_and_open(item="crafting_table")` (or `"furnace"`) puts the carried block on the
  ground one block ahead and opens its screen, moving it into the hotbar first when
  needed. Face flat ground with no screen open. To reopen a block placed earlier:
  `use_at(its coordinates)` with a NON-placeable item selected (your pickaxe) --
  right-clicking with a block in hand places the block instead.
- `furnace_load(item="iron_ore", n=0, fuel="auto")` fills the open furnace (n=0 = the
  whole stack; auto fuel = coal > charcoal > planks > logs > sticks) and does NOT wait;
  `furnace_take()` collects the output once ~200 ticks per item have passed, and refuses
  -- without clicking -- while the output cell is visibly empty.
- `mine_until(item="flint")` holds attack on the aimed block until that item lands.
Every macro starts with a gate (the right screen is open, the recipe's cells are empty)
and ends with a check; on failure it drops the rest of the plan and its [NOTE] names the
fix -- usually `stow_items` for leftovers in the grid, or reopening the screen. Do not
hand-roll a recipe with cursor_to_slot / gui_click when `craft` can do it; the primitives
below exist for RECOVERY (a stack stuck on the cursor, leftovers in a cell, an unusual
container) and for what no macro covers yet.

**The harness measures the cursor for you.** Every turn you are given a line like

    [CURSOR] container=(112.4, 61.0)px  over=inventory slot 12  off-inventory (in the
    cursor or in a crafting grid): oak_planks x4

That position is **measured from the frame** -- the rendered pointer is located in every
GUI tick's image -- so you never need to track or visually re-check the cursor. Trust
`over=` over your own read of the picture. The primitives are closed loop:
1. `cursor_to_slot(slot=<0-35>)` LANDS the cursor on a player inventory slot (the [INV]
   slot ids; 0-8 is the hotbar, 9-35 the three main rows). `cursor_to_cell(grid="3x3",
   cell=4)` lands it on a crafting cell; `cell="out"` is the output; `grid="furnace"`:
   cell 0 = the smelt input, cell 1 = the fuel slot, `"out"` = the result.
2. `gui_click()` picks up or drops a whole stack; `gui_right_click()` places one item.
3. {ground_truth_channels} are the ground truth
   for what a click did: **no [INV] line and no `craft_item`/`pickup` event means the
   click changed nothing**. The frame is not proof: it lags a tick and does not show what
   the cursor is holding.
4. The **[GRID]** line reads the frame at every grid slot's known position and lists the
   ones that visibly hold an item; read only your open screen's row. Leftovers in cells
   are retrieved with `stow_items(grid=..., cells=[...])` (banks the cursor stack too).

**A close that would drop items is refused.** Closing a screen while something is
off-inventory throws it on the floor -- it cost a previous run four of its five logs -- so
the runner turns that toggle into a no-op and writes a [NOTE]. Put the stack back in a
slot (`stow_items`), then close. If you *mean* to drop it, `{{"procedure":
"close_inventory", "args": {{"force": true}}}}`. A furnace KEEPS its cells across a close.

**Do not move while a table/furnace screen is open.** The game itself closes the screen
when you walk out of range (~5 blocks), and THAT close bypasses the runner's guard --
whatever the cursor held hits the floor. Stand ADJACENT to the block before opening it;
finish the recipe, close, then move.

**A click that worked can still read as no change for a frame.** The GUI applies clicks on
its own tick, so [INV]/[CURSOR] may lag one frame behind a click that in fact landed. On a
no-change reading, read the NEXT frame first; if two re-clicks in a row change nothing, the
state assumption is wrong (screen closed, cursor over the wrong cell) -- verify the open.

**An unplanned held stack gets stowed FIRST.** When [CURSOR] reports the cursor holding
something your current plan did not put there, one left-click on a confirmed-empty
inventory slot banks it (or `stow_items`). Every plan built on top of a surprise held
stack misclicks. A cursor move or click that finds the screen closed, a click whose
pointer is no longer where the last cursor move landed, or a left-click that lifts
nothing drops the rest of the plan with a [NOTE] saying so.

{skills_section}{chain_section}
Recipes available:
{recipes}

{procedure_notes}

**Survival** (a previous run died twice and lost everything):{survival_rule}
- A big health drop interrupts your plan with a [NOTE]; find the danger before resuming.
- If you die, the harness [NOTE] gives the death coordinates. Your items despawn there
  after ~6000 ticks: recover by stairs (never jump into a shaft) or rebuild -- decide by
  what is cheaper, and write the decision into your plan.

**Movement**:
- **Turn, then move.** A yaw change and "forward" in the same tick curve your path into an
  arc. Spend one entry turning, then several moving straight.
- `moved=0.00` repeatedly in [STATE] means you are blocked by terrain, not standing still
  by choice.
- Use sprint in the open. Use jump with forward to clear one-block rises.
- A raw attack-hold entry (attack with no movement keys) is cut short the moment a
  block breaks: the leftover ticks are refunded and a [NOTE] says so. To mine several
  blocks in a row use `mine_forward` / `strip_mine` / `stair_down`, which re-aim.
- Mining macros VERIFY their own movement (foot block, eye block, walk in, repeat) and
  end with a [NOTE] like "broke 9 blocks, advanced 4.1 blocks". Trust that number over
  your dead reckoning. "STOPPED EARLY ... did not move" means the passage is not
  opening: re-aim or change heading -- re-issuing the same call will stall the same way.
"""

SKILLS_SECTION = """\
**Skills by situation** (closed loop; each ends with a [NOTE] saying what happened):
- **Building** is BY COORDINATE from your exact position. `place_at(x, y, z, item)` puts a
  block into cell (x, y, z) by clicking a face of a neighbour (default: the block below it);
  `build_wall(item, length, height, dist)` builds a wall across your facing `dist` blocks
  ahead, `build_row(item, length)` a ground row running away from you, `build_column` one
  column, `bridge_forward(n)` a floor over a gap that you walk onto, `pillar_up(n)` a tower
  under your feet. Cells are block coordinates read off [STATE]: you stand in (floor(x),
  floor(y), floor(z)); "one block ahead" is z+1 at yaw 0, x-1 at yaw 90, x+1 at yaw -90,
  z-1 at yaw 180. Every placement is verified on `use_item`; a cell that is occupied, more
  than 4 blocks from your eye, or overlapping your own body is refused with the reason.
  Things that hang on a SIDE face (torches, item frames, paintings, ladders, signs, levers)
  go through `use_at(x, y, z, item, face=...)`, where `face` names the neighbour to click
  (a torch on the north side of a column at (x, y, z): target (x, y, z-1), face="south").
  Carpets, slabs, pressure plates, snow, flowers, saplings and seeds sit on a top face
  (the default). A door or a bed needs two free cells. A snow golem is two snow blocks
  stacked (`build_column(item="snow_block", height=2)`) with a carved pumpkin `place_at`
  on top. A nether portal is an obsidian frame 4 wide x 5 high standing on the ground: 10
  obsidian without the corners (two floor blocks, a column of 3 on each side, two across
  the top) around a 2 wide x 3 high inside that must stay AIR. Build it where you can step
  back from it -- clear a room at least 4 wide, 6 high and 3 deep with a flat floor -- with
  the 10 obsidian, a stack of cobblestone and the flint_and_steel in the hotbar; place the
  two floor blocks, then each column, then the top two standing on a cobblestone step beside
  a column, ONE `place_at` per cell, and after each read `[INV] obsidian -1` and look at the
  cell: a block that went elsewhere is mined back (diamond pickaxe) before the next. Light
  it from OUTSIDE with `use_at(<one of the two floor blocks>, item="flint_and_steel")`:
  the fire lands on its top face, inside the frame, and turns purple when the frame is
  right; orange flames that stay mean a wrong or missing cell (check all ten) or a block
  inside. Walk into the purple and stand still about 100 ticks; a [NOTE] confirms the Nether.
- **Using items on blocks**: `use_at(x, y, z, item)` -- a water_bucket / lava_bucket pours
  onto the clicked face, an empty bucket scoops a source block, flint_and_steel lights the
  top face, a hoe tills grass or dirt into farmland and seeds go onto the farmland, shears
  carve a pumpkin, bone_meal grows a sapling or crop; a bed, door, chest, table, furnace,
  lever or button is used with `item` omitted (whatever you hold stays selected).
  `use_held(item, hold)` holds right-click: a bow (hold >= 25 fires an arrow where you aim),
  a potion (32 ticks drinks it), a spyglass, a shield (blocks while held). `throw(item)`
  taps once for snowballs, eggs, ender pearls, eyes of ender. `eat()` eats the best food
  carried (only while the food bar is below 20).
  To FILL an empty bucket, call `fill_bucket()` at the shore: it holds the bucket and sweeps the crosshair over the ground ahead, tapping use until the inventory shows a water_bucket -- no cell or face to guess (use_at(bucket) needs the exact source block).
  When the water is across a clearing or behind trees, `fetch_water()` does the whole trip: it finds the blue in view (or looks around 12 headings), walks to the shore breaking the leaves in the way, and runs the sweep there -- go_to stops at the first obstacle and fill_bucket only reaches 4 blocks.
- **Containers**: a chest, barrel, furnace, brewing stand, enchanting table, stonecutter or
  crafting table opens with `use_at(its coordinates)`, holding a NON-
  placeable item; [GRID] then reads what its cells hold, and the one-call macros in the list
  above do the clicking: `craft`, `furnace_load` / `furnace_take`, `container_take` /
  `container_put` (chests, barrels), `brew` / `brew_take` (a brewing stand: water bottles +
  nether wart = awkward, then the effect ingredient; 400 ticks per step, every potion reads
  `potion` in the inventory), `enchant` (needs experience levels), `stonecut`. A chest,
  a brewing stand and a furnace keep their contents when their screen closes.
- **Entities** (mobs, animals, boats) are reported on NO channel: they are found in the
  frame by motion and colour. `face_entity()` centres the crosshair on the nearest moving
  thing (or `label=` a kind), `fight()` closes in and taps attack until a kill (or backs
  off at `retreat_hp`), `shoot_bow(shots)` draws and releases at it, `block_with_shield`
  holds a shield up, `use_on_entity(item)` right-clicks it with shears / a lead / a bucket
  / food / a fishing rod, or boards a placed boat (`boat_forward`, `leave_boat` after).
  A mob is hit by TAPPING attack (a held attack never lands); `kill_entity`,
  `damage_dealt` and hits (`use_item.<weapon>`) in the statistics prove a fight is
  landing, and a fight in progress is not interrupted by the hit reflex. Underground, a
  second hit within 30 ticks is a melee mob at arm's length: with a sword in your HOTBAR
  the runner turns you to face the shove and swings it (a sprint in a one-wide tunnel does
  not outrun a zombie); without one it sprints you away. Keep the sword in the hotbar
  whenever you dig.
- **Finding things**: `scan_around()` first (eight headings tiled into one image attached
  to your next turn), then `go_to(x, z)` toward what you saw, `travel(n)` along a heading,
  `look_abs(yaw=...)` to face a tile's yaw; `pillar_up(4)` before a scan doubles the view.
  On water, a boat is placed with `use_at(<a water block>, item="oak_boat")` and boarded
  by right-clicking it; forward drives it, sneak leaves it. A map is read by selecting it
  and looking at the frame; a compass needle points to the world spawn.
- **Pickup semantics**: `pickup` counts items picked up OFF THE GROUND; what comes out of a
  furnace or a crafting grid counts as `craft_item`. When a goal literally asks to pick up
  an item that was smelted or crafted, `drop_and_pickup(slot)` throws it at your feet and
  collects it again.
- **Time and weather** are not on the wire: read the sky in the frame. A bed works only at
  night (`sleep_in_bed(x, y, z)` skips the night).
"""

#: The from-scratch tech-tree doctrine (wood -> stone -> iron -> diamond and the mine),
#: rendered only when the task's milestone list is that chain: it is distilled from this
#: project's own diamond/dragon runs and would mislead a task that starts with a full
#: inventory.
_CHAIN_SECTION = """\
- **Wood first, and enough of it.** One trunk holds 4-6 logs, and 4 logs cover the whole
  wooden phase (a table, the pickaxe's planks and sticks, spare sticks for torches) --
  chop a full trunk BEFORE crafting anything rather than coming back for one log at a
  time. Wood is ONE call: `harvest_tree(logs=4)` walks at the trunk in view until it
  blocks you, chops until a log actually breaks, sweeps the drop and repeats -- by hand
  (aim_at_tree, chop_tree, walking) four chops in five broke nothing. It needs a TRUNK
  on screen: when its [NOTE] reports none, walk toward visible LEAVES first -- leaves
  always mark a trunk -- instead of re-running it from the same treeless view.
- **2x2 recipes** (planks, sticks, table, torches, flint_and_steel, blaze_powder, eye of
  ender) work in your own inventory: `open_inventory`, `craft(item)`, `close_inventory`.
- **3x3 recipes** (pickaxes, swords, furnace, bucket) need a crafting table's screen:
  `place_and_open(item="crafting_table")`, then `craft(...)`. Write the table's
  coordinates into your spatial model (it stands one block ahead of where you placed
  it, at your feet level) so it can be reopened later with `use_at`
  with the pickaxe selected -- a previous run spent 1,500 steps in front of its own
  table right-clicking with the table still in hand.
- **`mine_cobblestone` counts breaking a COBBLESTONE block, not natural stone.** Natural
  stone drops a cobblestone ITEM but the stat says `stone` and no milestone fires; a
  placed cobblestone block re-mined does count (~30 ticks).
- **Tools wear out**: wooden tools have 59 uses, stone 131, iron 250. [STATE]'s `Held:`
  line shows uses left.
- Every turn header states the budget: `Step N/MAX -- K steps remain`.
- **Iron ore needs at least a STONE pickaxe**, and the search for it is where
  from-scratch runs are decided: the runs that found iron searched 2,500-5,500 ticks
  of FRESH stone; the ones that did not searched 6,000-8,800 ticks over the same few
  hundred blocks, in the dark, near the surface. One descent, one mine level:
  1. Before going down, hold a stone pickaxe, 8+ spare cobblestone (a furnace at the
     face) and torches -- see the light rule below.
  2. Descend ONCE, with `dig_down(until_y=12)` (or `stair_down` where you want a
     walkable way back), and mine at y 11-12 for the rest of the run. In this
     Minecraft (1.16) iron spawns at the same density everywhere below y~63, so depth
     costs nothing for iron -- and y 11-12 is where diamonds (y 5-12) sit in the same
     tunnel walls, just above the lava lakes (y<=10). Never climb back up to smelt or
     craft: a fresh furnace is 8 cobblestone and a table 4 planks. A run once pillared
     41 blocks back up to its surface furnace with 50 cobblestone in hand -- 3,171
     ticks for one ingot.
  3. Strip-mine LONG, straight, lit 1x2 tunnels (`strip_mine(length=250)`) with a side
     branch every ~4 blocks; the area of NEW wall you expose is what finds ore. A site
     can be COLD: if two long lit strips have shown zero speckles, more of this tunnel
     multiplies nothing -- turn 90 degrees or move 30+ blocks and strip again. A run
     once spent its whole endgame extending one y-57 tunnel that produced a single
     sighting in 8,700 ticks.
  4. Lava: an orange glow on the walls means lava within a few blocks -- stop, do not
     dig down through the floor there, seal a flow with cobblestone, tunnel elsewhere.
     Lava is the one hazard that ends a run in seconds. The runner watches for it while
     you move below y 40: when lava fills more than ~1% of the lower view it drops the
     rest of your plan with a "LAVA AHEAD" [NOTE] and attaches the frame (_lava.png) --
     never re-issue the walk or dig that was stopped; go around or seal it first.
  The runner watches the walls during mining macros and stops with a [NOTE] when
  iron-ore-like speckles (tan dots on grey stone) or diamond-ore-like ones (cyan dots)
  cross the screen; the [NOTE] names which. On a sighting the
  runner also drops the rest of your plan (so the view holds still), saves the
  flag-time frame and attaches it to your next turn -- the [NOTE] names the file.
  Convert immediately: `aim_at_ore` centres the crosshair on the speckles, then
  `mine_ahead(n=120)` digs out exactly the aimed block (it never touches the camera;
  mine_forward would). And when `aim_at_ore` LOSES a flagged cluster ("no longer
  detected"), do not walk away: the ore face sits within a block or two of where the
  [NOTE] flagged it -- mine out the flagged wall segment by hand and sweep the drops.
  A run's only sighting of the night was abandoned exactly this way.
- **Carry the workshop down.** Before any descent the inventory holds a crafting_table
  (craft a second one rather than leave the only one behind), 12+ planks or 4+ logs, and
  8+ cobblestone: a table placed beside the ore is one `place_and_open`, a trip back to
  the surface for one is thousands of steps (one life: 12,000 steps between the
  diamond and the diamond pickaxe, spent looking for a table and a log). A table you
  placed and walked away from is gone for practical purposes.
- **Light BEFORE iron -- torches are eyes and armour.** Unlit tunnel walls render
  near-black (~4% brightness): the wall watcher and your own eyes are both nearly
  blind there, which is the main reason runs that strip-mine in the dark never see
  ore. And monsters spawn only in the dark, so a lit tunnel is one nothing walks up
  behind you in. Torches are 1 coal + 1 stick = 4 (2x2 grid, coal above stick). Coal
  is optional: **charcoal** is any log smelted in the furnace (`furnace_load(item=
  "oak_log", fuel="planks")`, ~200 ticks each) and crafts torches exactly like coal
  (`craft(item="charcoal_torch")`) -- 2 logs and 8 cobblestone are a lit mine, no coal
  vein required. Make 8+ torches before the
  descent and place one every ~8 blocks while strip-mining. Treat "no torches" as a
  blocker for the descent, the same way "no pickaxe" blocks mining.{strategy_bullets}
- **Smelting**: `place_and_open(item="furnace")` at the mine face, `furnace_load(
  item="iron_ore")` (the whole stack, auto fuel), `close_inventory`, keep mining, and on
  the next pass `use_at` the furnace + `furnace_take(item=
  "iron_ingot")`. Smelting runs with the screen open or closed, ~200 ticks per item.
  The `pickup` event for the ingot is what the milestone counts -- take the output.
- **After the iron pickaxe** the chain is diamond -> obsidian -> a lit portal -> the
  Nether, and every step has a macro: diamonds sit at y 5-12 in the same strips (a
  diamond pickaxe is 3 diamonds + 2 sticks; a diamond sword 2 + 1). **The bucket comes
  FIRST**: the moment you hold 3 spare iron ingots (right after the iron pickaxe, before
  any descent for diamonds), craft the bucket and fill it at still water on the surface
  (`fetch_water()` walks to the water it sees and fills it there), then carry the
  water_bucket down; 43 second-half runs that descended first never came back up for
  water. Never dig a shaft beside the water you filled at (it floods): walk 8 blocks
  away first. **Obsidian** is made where lava LAKES are -- the open orange pools at
  y <= 11, not a corridor: strip-mining at y 11-12 walks past them and the runner's
  "LAVA AHEAD" [NOTE] names the pool cell and the rim cell the moment one fills the
  lower view; with the water_bucket carried that sighting IS the plan: `make_obsidian()`
  (no arguments: it pours on the sighting's rim and scoops the source back), then
  `mine_obsidian()` (no arguments: the sighting's pool cell, ~190 ticks of held attack,
  FIRST in its plan) with the DIAMOND pickaxe. Pour
  only once the lava is IN VIEW and the LAVA AHEAD note has named the cells -- a
  `make_obsidian(x, y, z)` with no lava in view is refused as a blind pour (three lives
  poured on stone in the dark and two died there).
  `find_lava()` is the blind search for when
  nothing is known: it tunnels in legs at about y 11 and stops 2 blocks short of the
  first pool it sees; it is slow (about 25 blocks per call) and needs 250+ ticks FIRST
  in its plan. **The portal** needs 10-14
  obsidian and flint_and_steel (1 iron + 1 flint from gravel): stand on flat ground
  with 4-8 cobblestone in the hotbar, `build_portal_frame()`, `light_portal()`,
  `enter_portal()`; the [NOTE] confirms the Nether. There, `netherrack` is the ground
  (mine one: `mine_until(item="netherrack")` is the pickup), **blazes** live in the
  black-brick fortresses (a rod each, `fight` them; blaze_powder = 1 rod in the 2x2),
  **endermen** wander the Nether's red/blue forests and the Overworld at night (a
  pearl per kill, roughly one in two; never look them in the eye until you are
  ready to fight), and `ender_eye` = blaze_powder + ender_pearl in the 2x2. Coordinates
  in the Nether are the Overworld's divided by 8; the same portal takes you back.
- **In the Nether, the walk has macros too.** A fortress is a long nether-brick
  (dark red-brown) structure running along the x or z axis, so one leg per axis finds
  one: `explore_nether(axis="x", sign=1, length=80)` holds the heading, tunnels through
  netherrack when a wall stops you, sneaks and bridges with your cobblestone when lava
  fills the lower view, and STOPS with a note the moment nether brick or a blaze is in
  view, giving the bearing -- then `look_abs(yaw=<bearing>)`, `travel`/`go_to` toward
  it. Carry 16+ cobblestone and a pickaxe for it. `fight_blaze()` is the fight for a
  blaze (the plain fight's yellow is also lava's): it walks in under the hovering mob
  and pulses attack; a blaze shoots fire from range, so keep health above 10 and put a
  wall between you and it when hurt; then `collect_drops` for the rod (one kill in two
  drops one). An enderman (three blocks tall, 40 hp) cannot hit what stands two blocks
  below its feet: `enderman_pit()` digs a 2-deep pit under you and looks up; from the
  pit, look at it (that is what angers it) and `fight(label="enderman")` its legs, then
  `pillar_up(2)` out and `collect_drops` for the pearl. Endermen are common in the
  Nether's warped forest (blue) and appear in the Overworld at night.
- **The stronghold and the End** (after the eye of ender), every step a macro: in the
  open, `throw_eye()` throws one eye, watches it and reports the yaw it flew toward and
  whether it CLIMBED (the stronghold is far that way -- `travel_bearing(yaw, blocks=100)`
  and throw again) or DROPPED (it is below you: `dig_down` there). Every throw uses
  the eye up (it does not drop back here): carry two or three spare eyes for the
  search on top of the twelve-minus-prefilled the portal takes. The stronghold is stone brick; its portal
  room has 12 frames around a 3x3 lava pit: `fill_end_portal(x, y, z)` (the pit's
  middle cell, y = the frames' level) walks the ring and puts an eye in every empty
  frame (a frame that refuses one already has it -- 12 eyes at most, fewer usually);
  when all 12 hold an eye, `enter_end(x, y, z)` jumps in. You land on an obsidian
  platform near x 100, z 0; the island is toward x 0 (the note gives the yaw) and its
  pale ground is **end_stone**: `mine_end_stone()`. The dragon heals from the **end
  crystals** on the obsidian towers: `break_crystal()` (bow + arrows from a distance;
  hitting one by hand blows up in your face), then `attack_dragon()` when it perches on
  the bedrock fountain at the centre (its head takes full sword damage, the body a
  quarter).
"""

# -- per-memory-mode substitutions for the shared reference ---------------------------
#
# The action/perception reference above is the SHARED substrate of the comparison:
# the arms must read the same words wherever the same mechanism is being
# described. The only lines allowed to differ are the ones that name a memory surface,
# and each of those is a parameter with one value per mode, defined together here so a
# diff of this block *is* the protocol difference.

_GROUND_TRUTH_CHANNELS = {
    "mfm": "The [INV] and [EVENT] lines in `logs.txt`",
}
# The direct arm has no filesystem and no feedback lines: the game's own numbers reach
# it only as the present state of each turn message.
_GROUND_TRUTH_CHANNELS["direct"] = ("The Milestones block and the Inventory line in "
                                    "your turn message")

# What the JSON action plan is called where it is referenced. The file-backed arms write
# it as `actions.json`; the direct arm has no tools, so the same JSON travels in the
# reply's last fenced block.
_ACTIONS_CHANNEL = {
    "mfm": "`actions.json`",
    "direct": "your actions JSON",
}

# The worked example is identical in every arm on purpose: the *practice* of writing
# down a landed sequence is shared knowledge; where the note lives is memory design.
_PROC_NOTE_EXAMPLE = """\
    # iron at the face (one visit, no climbing)
    Preconditions: 3+ iron_ore, 8 cobblestone, 4 planks, 2 sticks; stone pickaxe held.
    1. place_and_open(item="furnace"), furnace_load(item="iron_ore") -> [NOTE] "3 in
       the smelt cell, 2 planks in the fuel cell"; close_inventory; strip_mine 600 ticks
    2. use_at(furnace x, y, z), furnace_take(item="iron_ingot")
    3. place_and_open(item="crafting_table"), craft(item="iron_pickaxe"), close_inventory
    Failure seen: place_and_open on a slope put the table out of reach -- flat ground first."""

_PROCEDURE_NOTES = {
    "mfm": f"""\
**Write down what worked.** The moment a GUI sequence lands -- a recipe crafted, an item
moved where you wanted it -- put it in your briefing before the detail is gone: the
harness writes your briefing and [PLAN] into `logs.txt`, and that is the only place it
survives. Not a summary of the recipe layout; what goes in is the part you cannot
re-derive from a picture:

{_PROC_NOTE_EXAMPLE}

Address slots and cells by number, not by offset. Grep the log for your own earlier
briefings before crafting anything a second time. This is the difference between solving
a recipe once and solving it every time.""",
    # The same worked example, because it is task knowledge every arm carries; the
    # direct arm gets it without any memory practice attached -- there is nowhere to
    # write it and nothing of its own to re-read.
    "direct": f"""\
**Address slots and cells by number, not by offset.** The part of a GUI sequence you
cannot re-derive from a picture is the exact route through it -- for example:

{_PROC_NOTE_EXAMPLE}""",
}

# The log protocol, restated after PRO-LONG's: one append-only log the model greps.
# `_mfm_contract` turns it into the mfm arm's memory section by swapping two passages
# (the tool line and the "Nothing else persists" paragraph).
_LOG_CONTRACT = """\
**Your memory is one append-only log.** `./logs.txt` persists for the whole episode and
across turns, and it is the ONLY thing that does. You are expected to read it
programmatically -- it is far too large to read by eye, and reading it by eye is exactly
the error this design exists to avoid.

    logs.txt              append-only: every action, the state that followed, your own
                          prior briefings and plans. GREP THIS. Do not read it whole.
                          `rg -n` line numbers are NOT step numbers -- the step is in
                          each block's "Action N | Step M" header. A previous run wrote
                          line numbers into its notes as steps and chased events that
                          never happened. [EVENT] lines in it came from the game's own
                          statistics: a craft with no [EVENT] line did not happen. You
                          cannot edit this file.

Nothing else persists: any other file or directory you create in `./` is removed when
your turn ends, and no earlier frame is kept -- the current view is attached to this
call and it is the only image you have. Whatever you will want to find again goes in
your briefing and [PLAN], which the harness writes into the log.

**Tools**: Read, Bash, Grep, Glob to read the log; Write to create `actions.json`, which
is **deleted before your turn starts**. Create it; do not edit it. An edit is an update
to a file that is not there, it is rejected, and you spend the retry -- 77% of turns in
one run were paying for this.
"""

# Strategy distilled from this project's own failed runs -- resource planning, route
# discipline, endgame ordering.
_STRATEGY_BULLETS = """
- **Plan your wood trip once**: the early tree needs ~3 logs (4 planks for the table,
  3 planks + 2 sticks for the pickaxe, 1 log spare). Chop them from ONE tree before
  crafting anything -- four runs lost 1,900-3,000 steps re-finding trees after
  spending their single log, in two different tasks. Get them with `harvest_tree`
  (logs=4, one call, closed loop) rather than aim_at_tree -> chop_tree -> walk -> chop
  by hand; keep chop_tree for a single block you are already touching.
- **Plan your stone trip once**: the tech tree needs 3 cobblestone for the stone pickaxe
  AND 8 for the furnace. Mine 11+ before climbing back -- the run that banked its
  furnace cobblestone in the same trip crafted the furnace 68 steps after the pickaxe;
  the one that took the minimum spent its whole endgame going back down.
- **Craft the NEXT pickaxe before the current one breaks**, and keep a reserve of 1 log
  (or 4 planks + 2 sticks) unspent -- one run's wooden pickaxe broke mid-descent with 3
  planks left: 22 cobblestone in hand and no way to craft a table, a pickaxe or a
  furnace for the remaining 900 steps.
- **Bank the endgame**: under ~800 steps remaining, stop exploring and bank the cheapest
  unmet milestone (a furnace is one table visit with 8 cobble; `mine_cobblestone` is one
  placed block -- take that credit as soon as you hold any cobble).
- **Do not walk back to old blocks.** A crafting table is 4 planks and a furnace 8
  cobblestone -- place FRESH ones at the mine face instead of returning to the surface.
  One run spent 2,350 steps tunnelling back up to a table it could have rebuilt for
  four planks it was carrying.
- **The free-slot count on the Inventory line is exact, and at 0 every new drop is
  LOST** -- the ore you just mined vanishes on the floor (a run mined 3 iron ore with a
  full inventory and picked up 1). Throw junk away with `discard_stack(slot=N)` as soon
  as free slots fall to ~3: dirt, gravel, granite, diorite, andesite, cobblestone
  beyond one stack. Never bank junk in a furnace or place it block by block for room.
- **Cheap milestones off the main chain**, when your list has them: `flint_and_steel`
  is 1 iron ingot + 1 flint in the 2x2 grid, and flint drops from GRAVEL (about 1
  block in 10, any tool: aim at a gravel bank, `mine_until(item="flint")`). Gravel
  you carry can be PLACED and broken again -- every break is a fresh 1-in-10 roll,
  so 3-4 gravel blocks re-broken a few times give the flint without a search; gravel
  lies in pockets underground, in river beds and on beaches. Bank flint_and_steel
  with the first spare ingot rather than after the diamond chain.
- **The furnace runs while you mine.** Smelting takes ~200 ticks per item whether you
  watch it or not: load ALL banked ore and enough fuel in ONE visit, walk away to keep
  mining, and collect the ingots on the next pass. Do the chain arithmetic before
  climbing anywhere -- an iron pickaxe is 3 ingots, so bank 3+ ore and smelt them as
  one batch. Runs that shuttled ore one item at a time to an idle furnace, or stood
  watching it smelt, paid their whole mid-game to logistics; one never crafted the
  iron pickaxe at all.
- **The crafting table is portable**: mine the placed table (~40 ticks, any tool) and
  it drops as an item -- carry ONE table for the whole run and re-place it at each new
  base instead of spending 4 planks on a fresh one."""

_SURVIVAL_RULE = """
- **What kills runs: monsters in unlit tunnels, then drops into caves and ravines.**
  Every death on record was one of the two. Monsters are not reported on any channel
  here (`Nearby entities` always reads "not reported"), so the only warning is the
  health drop -- and a stationary miner in the dark takes 4-5 damage every few seconds
  until it dies; a run read five such hits as "a short fall" and kept digging.
  Prevention: torches (above) and a 1x2 tunnel with its ceiling intact. **Reflex on a
  hit**: the runner interrupts your plan, turns you 180 degrees to face where the hit
  came from, and attaches both frames (the moment of the hit, and the view after the
  turn). Then: a monster in view -> hold `attack` on it (a pickaxe works; a stone
  sword is 2 cobblestone + 1 stick), because fleeing down a 1-wide tunnel just leads
  it after you; a fall -> do not jump back down; an orange glow -> lava, back away and
  seal it with cobblestone. A slow steady loss (drowning, burning, starvation) is
  reported the same way; read the Vitals line. Two attackers are not "hold attack":
  a **skeleton** shoots from range (2-4 damage per arrow, steady), so break its line
  of sight -- two cobblestone between you and it, or step out of the tunnel -- and
  never charge it under 10 health (a run at 4 hearts rushed one and died); **cave
  spiders** (cobwebs = an abandoned mineshaft) poison and swarm, so leave the shaft
  the way you came and wall it off; an **enderman** that you look in the eye from under 4 blocks teleports away, so once one is close keep the crosshair on its body or legs, never on its head. While hits keep coming, a plan that MOVES you
  keeps running (that is your escape), but a plan standing still -- digging,
  sweeping, clicking -- is stopped by the runner, and at 6 health or less
  everything is: get out of reach first (pillar up two blocks, or wall the tunnel).
  At 6 hp or less the runner does the pillar itself, on any cobblestone/dirt/planks
  in your HOTBAR -- keep a stack there -- and hands you the view from the top.
  Underground (y below 50) a pillar has no headroom, so at 10 hp or less the runner
  BUNKERS you instead: digs two blocks straight down with the pickaxe in your hotbar
  and caps the hole with the block -- keep both in the HOTBAR while mining. From the
  capped hole, heal, then look_abs(pitch=-90) + mine_ahead breaks the cap and
  pillar_up(2) climbs out.
- **The fall hazard is what opens under your feet, not the depth itself.** Digging
  straight down can drop you into a cave or lava -- so descend with eyes open (the y
  readout updates every step; stop at the first lava light), not slowly. `dig_down`
  with `until_y` is the descent that has actually reached ore depth; `stair_down`
  leaves a walkable way back up. A hole you dug and then walked or jumped back into
  is the second most common death: stairs, or pillar down placing blocks, never a jump.
- When ore does appear, EXHAUST the vein before leaving: veins run 2-8 blocks (check
  every face of the hole), and count what the chain needs -- an iron pickaxe is 3
  ingots, so 2 ore banked is a milestone but not a pickaxe. A run once spent its last
  5000 steps hunting ore #3 after walking away from the find. And when you travel to a
  site by its coordinates, verify ARRIVAL against the live position readout -- within ~3 blocks
  on x and z -- before drawing any conclusion about the site: a run once planned the
  same walk to a proven vein all night, called the vein absent, and had never come
  closer than 23 blocks.
- **The Nether lock.** Every Nether visit on record died within 400 steps of arriving,
  walking, sprinting or jumping down a slope or off a ledge into the lava sea (y ~31).
  There the runner holds sneak on every step you take (a quarter of the walking speed),
  never sprints, drops a jump taken while moving, and DROPS any plan entry that has
  walked you a block down with lava in the lower view (NETHER DESCENT). A one-block
  rise is tunnelled or pillared; go DOWN by digging (stair_down), never by walking or
  jumping; cross lava with bridge_forward; a hit there is answered by the bunker, the
  pillar or the turn, never a sprint."""


_SURVIVAL_GENERIC = """
- **Monsters and falls end runs.** Nothing reports monsters on any channel; the only
  warning is the health drop, and the runner reacts to a hit: it interrupts your plan,
  turns you to face where it came from, attaches the hit frame, and at 6 hp or less
  pillars you up on any block in your HOTBAR (underground at 10 hp or less it digs a
  two-block hole and caps it instead; in the End it only turns you -- the island's
  edge is the void, so stand and fight there; when the frame shows lava filling the
  lower view the damage is the lava itself, and it pours your water bucket at your
  feet if one is in the hotbar and steps you back instead). Then fight (the entity
  macros) or leave; an **enderman** that you look in the eye from under 4 blocks teleports away, so once one is close keep the crosshair on its body or legs, never on its head;
  never stand still in the dark. A slow steady loss is drowning, burning or starvation --
  read the Vitals line; with water around you (or afloat) the runner holds jump to swim you
  up, and it refuses dig_down / stair_down within 6 blocks of water seen in the last 200
  ticks -- a shaft beside a pond floods. Never jump down a hole you cannot climb out of.
- **The Nether lock.** Every Nether visit on record died within 400 steps of arriving,
  walking, sprinting or jumping down a slope or off a ledge into the lava sea (y ~31).
  There the runner holds sneak on every step you take (a quarter of the walking speed),
  never sprints, drops a jump taken while moving, and DROPS any plan entry that has
  walked you a block down with lava in the lower view (NETHER DESCENT). A one-block
  rise is tunnelled or pillared; go DOWN by digging (stair_down), never by walking or
  jumping; cross lava with bridge_forward; a hit there is answered by the bunker, the
  pillar or the turn, never a sprint."""


#: `--no-harness-reflexes` (skills.py): the hazards without the runner's reflexes -- in
#: that run nothing acts on a hit, a fall or lava but the model's own reflexes.
#: `_SURVIVAL_OWN`, by whether the arm has reflexes of its own.
_SURVIVAL_TICK = {
    True: ("Your reflexes under `mine/reflexes/` are the tick layer\n"
           "  (`skills/reflexes/SKILL.md`), and your"),
    False: "Your",
}

_SURVIVAL_OWN = """
- **What kills runs: monsters in unlit tunnels, drops into caves and ravines, lava met
  while moving, and in the Nether every ledge into the lava sea.** Monsters are reported
  on no channel; the health drop is the only warning, and a plan standing still under
  hits (digging, sweeping, clicking) is how most deaths began. In THIS run the runner
  does not act for you: no stop at lava, no pillar or bunker on a hit, no swim-up, no
  refusal of a repeated plan. {tick} plans carry the doctrine: torches and a 1x2
  tunnel with its ceiling intact; a sword in the hotbar before going deep and food in
  the inventory (no natural healing below 18 food); descend by stairs, never by jumping
  into a hole; back away from orange and seal it with a block; break a skeleton's line
  of sight instead of charging it; an **enderman** that you look in the eye from under 4 blocks teleports away, so once one is close keep the crosshair on its body or legs, never on its head; in the Nether sneak, never sprint or jump while
  moving, dig the way down, bridge over lava. Verify ARRIVAL at a remembered place
  against the live position readout before drawing conclusions about the site.
- **Obsidian is lake work, and a death there costs the chain its tools.** Obsidian breaks
  only under a DIAMOND pickaxe (any other tool breaks it with no drop) and lies where
  water met lava, so the pool is beside every cell: a mined cell is a HOLE over it --
  never step on or across one, fill it with cobblestone, and take the drop from the edge.
  Before the lake, leave the spare diamonds, the flint and steel and any second pickaxe in
  a chest at the base: what you carry burns when you die there, and without a diamond
  pickaxe the chain is back at the diamonds. Where a sheet cannot be mined safely, water
  poured onto a lava SOURCE casts obsidian in place. Your reflexes are quiet while a
  screen is open: at the lake never pour, craft or sort from the inventory screen -- a
  life at 8 health did, took the lava's 4 with the screen up, and died pillaring at 4.
  A bed (3 wool from sheep + 3 planks;
  `use_at` it at night) skips the night and moves your respawn to it -- set one by the
  work site before the lake and the portal, so a death costs a walk of ten blocks, not
  two hundred, and the drops are still there.
- **A death at night is followed by another.** You respawn at the world spawn, at the
  surface, with nothing, and what killed you is still out there: of 33 deaths in four
  lives, 18 were at the surface and 22 were mobs, seven in a row in one night. After a
  respawn in the dark, dig two blocks down where you stand (or wall yourself in with
  anything) BEFORE a single step, and walk only in daylight; the drops wait ~6,000
  ticks, the night is 12,000. The bed is the first thing to make once you have seen a
  sheep -- no life of the record ever made one."""


# The direct arm's contract: no memory of any kind -- no filesystem, no tools, no
# window of earlier turns, no feedback from the last batch. The model plays each turn
# from the present alone: the same state block the memory arms get and the current
# view. Nothing here tells it what it cannot keep; there is simply nothing to keep.
_DIRECT_CONTRACT = """\
**You have no tools and no filesystem this run**: everything happens in your reply. Each
turn message shows you the game's own numbers for RIGHT NOW (milestones, [STATE],
inventory, vitals, cursor) and the current view as an attached image. The reference
below describes [NOTE] and [INV] lines the harness writes after an action; in this run
none of them is delivered to you. Read what an action did from the next turn message:
Milestones, Inventory, [STATE] and the attached view.
"""

# The direct arm's response contract: the same JSON schema the other arms put in
# actions.json, carried in the reply because there is no Write tool to carry it.
_DIRECT_OUTPUT_CONTRACT = """\
Then end your reply with ONE fenced code block containing the actions JSON:

    ```json
    {"actions": [{"action": {...}, "repeat": N}, ...]}
    ```

The LAST fenced JSON block in your reply is the one executed. Do not write files -- you
have no tools; a reply with no valid fenced JSON block executes nothing and costs the
turn."""

ACT_PROMPT = """\
You are an embodied agent playing Minecraft, controlling a player by writing action plans.

**Task**: {task_text}

{scoring_line}

{progress_block}

{memory_contract}

{world_model_docs}

**What you can rely on**:
- `[STATE]`'s yaw is CUMULATIVE, not wrapped: after enough turning it reads values like
  810 (= 810 - 720 = 90). Reduce it mod 360 before any heading arithmetic of your own;
  the closed-loop skills (look_abs, look_at, go_to) already handle it.
- Coordinates and facing in `[STATE]` are ground truth. Your read of a frame is not proof
  an action worked.
- {ground_truth_bullet}
{belief_rules}
{graph_section}
{plan_section}
{discipline_section}

**Response format**: a short strategic briefing, then

[PLAN]
{plan_line}

{output_contract}

{action_reference}
"""

_SCORING_LINE = {
    True: "This is a long-horizon task scored by how far down an ordered milestone list you "
          "get. The\nenvironment verifies each milestone from the game's own statistics -- "
          "you do not get to\ndecide you have achieved one.",
    # Wording deliberately neutral: it says what the episode is, not what any grader
    # looks for (audit).
    False: "This task has no milestone list: it is judged on what you actually accomplish in "
           "the episode,\nas a human player would do it. Plan from the task text, do the "
           "thing completely, and verify\neach step on the game's own statistics ([EVENT] / "
           "[INV]) rather than on your read of the\nframe. The episode runs its full length "
           "either way; once the task is done, do not start\nunrelated work.",
}


def task_family(milestone_cfg) -> str:
    """'from_scratch' when the milestone list is the wood -> stone -> iron tech tree this
    project's mining doctrine was distilled from; 'general' for everything else (a task
    with no milestones, or milestones about combat, collecting, using items)."""
    ids = {str(c.get("identity", "")) for c in (milestone_cfg or []) if isinstance(c, dict)}
    return ("from_scratch" if ids & {"mine_log", "crafting_table", "wooden_pickaxe",
                                     "stone_pickaxe", "mine_iron_ore", "iron_pickaxe",
                                     "diamond"} else "general")


_GROUND_TRUTH_BULLET = {
    "mfm": "The [EVENT] lines in `logs.txt` are ground truth. "
               "Your memory of what you crafted is not.",
}
_GROUND_TRUTH_BULLET["direct"] = ("The Milestones block and the Inventory line in your "
                                  "turn message are ground truth. A craft that does not "
                                  "show there did not happen.")

_PLAN_LINE = {
    "mfm": "<2-3 sentences: what you are doing next and what observation will tell "
               "you it worked>",
}
_PLAN_LINE["direct"] = _PLAN_LINE["mfm"]

_OUTPUT_FILES = {
    "mfm": """\
- `./actions.json` -- REQUIRED. `{"actions": [...]}`, see below.""",
}

# The paragraph `_mfm_contract` swaps out: the "nothing else persists" clause becomes
# the description of `episodes/` (mcu_worldmodel/episodes.py, beside the store it
# describes).
_LOG_NOTHING_ELSE = """\
Nothing else persists: any other file or directory you create in `./` is removed when
your turn ends, and no earlier frame is kept -- the current view is attached to this
call and it is the only image you have. Whatever you will want to find again goes in
your briefing and [PLAN], which the harness writes into the log.
"""
assert _LOG_NOTHING_ELSE in _LOG_CONTRACT

#: The log protocol's tool line (no image tool) and the mfm arm's, which
#: names `view_image` and what it can be pointed at. Earlier the mfm contract
#: kept the first line verbatim: view_image was never listed, and across several runs the
#: model pointed it at zooms of the current view 250 times, at an earlier episode's frame
#: 32 times, at an earlier life's frame 3 times.
_LOG_TOOLS_LINE = ("**Tools**: Read, Bash, Grep, Glob to read the log; Write to create "
                       "`actions.json`, which")
assert _LOG_TOOLS_LINE in _LOG_CONTRACT
_MFM_TOOLS_LINE = ("**Tools**: Read, Bash, Grep, Glob to read the log and the episode index; "
                   "`view_image <png>` to LOOK at a frame -- the attached view, any episode's "
                   "`observation/image.png` (this life's or an earlier life's under "
                   "`previous/`), a sheet from `--sheet`{zoom}; Write "
                   "to create `actions.json`, which")


def _own_mod():
    from mcu_worldmodel import own
    return own


def _mfm_contract(retrieval: bool = False, previous: bool = False, expect: bool = False,
                  frames: bool = False, own: bool = False, own_reflexes: bool = False,
                  harness_reflexes: bool = True) -> str:
    from mcu_worldmodel.episodes import (MFM_EXPECT_NOTE, MFM_FRAMES_NOTE, MFM_MEMORY_NOTE,
                                         MFM_RETRIEVAL_NOTE)
    from mcu_worldmodel.previous import MFM_DIGEST_NOTE, MFM_PREVIOUS_NOTE
    note = (MFM_MEMORY_NOTE + ("\n\n" + MFM_RETRIEVAL_NOTE if retrieval else "")
            + ("\n\n" + MFM_PREVIOUS_NOTE if previous else "")
            + ("\n" + MFM_DIGEST_NOTE if (previous and own) else "")
            + ("\n\n" + MFM_EXPECT_NOTE if expect else "")
            + ("\n\n" + MFM_FRAMES_NOTE if frames else "")
            + ("\n\n" + _own_mod().MFM_OWN_NOTE if own else "")
            + ("\n\n" + _own_mod().MFM_WORKING_NOTE if own else "")
            + ("\n\n" + _own_mod().reflex_note(harness_reflexes) if (own and own_reflexes) else ""))
    scope = "outside `mine/` " if own else ""
    text = _LOG_CONTRACT.replace(
        _LOG_TOOLS_LINE,
        _MFM_TOOLS_LINE.format(zoom=", a crop from `tools/zoom.py`" if frames else ""))
    text = text.replace(_LOG_NOTHING_ELSE, note + f"""

Any other file or directory you create in `./` {scope}is removed when your turn ends; the
current view is attached to this call, and the earlier views are the episodes' images.
Whatever you will want to find again goes in your briefing and [PLAN], which the
harness writes into the log and into the episode{", or in `mine/`" if own else ""}.
""")
    return text


#: `--thin`: the standing contract keeps the task, the memory protocol, the response
#: format, the action schema and the procedure index; these sections (by their heading)
#: move to `references/<file>` in the workspace, read on demand. Modelled on the
#: SKILL.md + references layout of wz1119/Codex-Minecraft-Gameplay: one
#: page of loop and rules, the long tables next to it. The mfm AGENTS.md was 14,300
#: words; a session reads it once, a turn message points back into it.
_THIN_MOVED = (
    ("**Crafting is ONE call.", "gui.md"),
    ("**The harness measures the cursor", "gui.md"),
    ("**A close that would drop items", "gui.md"),
    ("**Do not move while", "gui.md"),
    ("**A click that worked", "gui.md"),
    ("**An unplanned held stack", "gui.md"),
    ("**Skills by situation", "skills.md"),
    ("**Write down what worked", "skills.md"),
    ("**Survival", "survival.md"),
    ("**Movement", "survival.md"),
    ("# The benchmark's own control reference", "control.md"),
)
_THIN_PROCEDURES = "**Procedures**"
_THIN_FILES = {
    "procedures.md": "every procedure in full -- what it does, its preconditions, its "
                     "parameters, and the notes on using them",
    "gui.md": "the GUI and crafting rules (one-call crafting, the measured cursor, "
              "refused closes, held stacks)",
    "skills.md": "the skills by situation -- which procedure for wood, stone, iron, "
                 "diamonds, water, lava, the portal, the Nether, the End -- and what to "
                 "write down",
    "survival.md": "survival (mobs, hunger, falls, deaths) and movement",
    "control.md": "the benchmark's own control reference (raw keys, camera, JSON schema)",
    "more.md": "everything else that was moved out of this contract",
}
_THIN_HEADING = re.compile(r"^(\*\*[^*]+\*\*|#{1,3} )")

#: The loop, after the "Plan and act" / "Inspect and recover" sections of
#: wz1119/Codex-Minecraft-Gameplay's SKILL.md (Apache-2.0; agents/skills/minecraft-gameplay/
#: SKILL.md), in this harness's vocabulary: their "final image" and pixel
#: checks are our next turn's [STATE]/[INV]/[EVENT] lines and the attached view.
_THIN_LOOP = """\
**Loop.** Every turn: observe, plan, act, verify.
- *Observe*: classify the situation from the turn message and the view -- a screen open or
  gameplay, footing (solid, a drop, water, a slope), the selected item, what you carry,
  what is reachable. Resolve the state from THIS turn's numbers, never from what you
  intended last turn.
- *Plan*: choose the milestone from the task and what you actually hold. Budget tools,
  materials, light and the way back before committing to a longer route. Establish one
  useful short action first; extend only across ground you have seen or a screen the
  harness has measured.
- *Act*: bounded entries; separate looking from sustained mining; verify clearance before
  advancing; use the right tool for the material. Before a craft, check ingredients,
  quantities and the cursor; after it, check the output in [INV].
- *Verify*: read what the last plan did from [OBSERVED], [INV], [EVENT] and the view, and
  say in one sentence whether it matched. Distinguish "the entries ran" from "the
  objective advanced". A plan cut short can have moved you, spent items or half-done a
  craft: continue from a fresh observation, never replay a resource-consuming prefix
  blind. When movement stalls, inspect footing and reachable space (`[MAP]`, the view)
  before extending holds or mining more; `watch(until=..., n)` is the observe step
  between acting and deciding.
"""


def thin_split(contract: str, tools: bool = True,
               safety: str = "") -> tuple[str, dict[str, str]]:
    """(short contract, {reference file: text}). Sections are cut at their headings;
    from the first moved heading on, every section goes to a reference file (unknown
    headings to more.md). Without `tools` (the direct arm) the moved text is
    dropped."""
    lines = contract.splitlines()
    blocks: list[list[str]] = [[]]
    for ln in lines:
        if _THIN_HEADING.match(ln) and blocks[-1]:
            blocks.append([])
        blocks[-1].append(ln)
    kept: list[str] = []
    refs: dict[str, list[str]] = {}
    moving = False
    for b in blocks:
        head = b[0] if b else ""
        target = next((f for pre, f in _THIN_MOVED if head.startswith(pre)), None)
        if target is not None:
            moving = True
        if not moving:
            if head.startswith("**Task**"):
                kept.extend(b)
                if kept and kept[-1].strip():
                    kept.append("")
                kept.append(_THIN_LOOP)
                if safety:
                    kept.extend([safety, ""])
                continue
            if head.startswith(_THIN_PROCEDURES) and tools:
                # The procedure index stays; the full reference (docs, preconditions,
                # the notes on each) is a file -- 5,700 of the contract's 14,300 words.
                from mcu_worldmodel import procedures as P
                kept.append(head)
                kept.append(P.index())
                if P.VISIBLE is not None:
                    kept.append(_own_mod().atoms_line())
                kept.append("Full descriptions, preconditions and the notes on each: "
                            "`references/procedures.md`.")
                kept.append("")
                refs.setdefault("procedures.md", []).extend(b)
                continue
            kept.extend(b)
            continue
        f = target or ("control.md" if head.startswith("#") else "more.md")
        refs.setdefault(f, []).extend(b)
    if not refs:
        return contract, {}
    files = {f: "\n".join(v).strip() + "\n" for f, v in refs.items()}
    if tools:
        listing = "\n".join(f"- `references/{f}`: {_THIN_FILES.get(f, f)}" for f in files)
        tail = ("\n\n**References.** This contract is short on purpose. The full rules "
                "live next to it, harness-written and immutable, in `references/`:\n"
                + listing
                + "\nRead the relevant file (Read/Grep) before the first action of that "
                  "kind this run -- a GUI sequence, a descent, a fight, a pour -- and "
                  "again when a procedure's [NOTE] says it was refused. The harness's "
                  "[NOTE]/[EVENT]/[STATE] lines are facts; the references say what to "
                  "do about them.\n")
    else:
        tail = ("\n\n**Kept short.** The GUI, skills, survival and control references "
                "are not in this run's contract; the procedure descriptions above and "
                "the milestone block are what you have.\n")
        files = {}
    return "\n".join(kept).rstrip() + tail, files


def platform_block(platform_prompt: str,
                   actions_channel: str = "your `actions.json`") -> str:
    """Frame the host benchmark's own agent contract for inclusion in the act prompt.

    MCU-AgentBeats sends every purple agent a control reference in `InitPayload.prompt`
    (`src/prompt.txt`): key semantics, the mutually-exclusive movement constraints, the
    camera sign convention, hotbar single-selection, and the GUI/cursor measurements. When
    this package runs as its own in-process runner there is no such field; when it runs as
    a purple agent there is, and folding it in is what makes "same input, different memory
    mechanism" true rather than aspirational.

    The one conflict is the response format: the host document ends by asking for a single
    flat JSON action object, which is right for a one-action-per-step agent and wrong here.
    It is reconciled explicitly, because a plan written in the host's shape does not parse.
    NB: this return value is substituted as a *value* and never itself passed through
    `.format()`, so braces are literal.
    """
    text = (platform_prompt or "").strip()
    if not text:
        return ""
    return (
        "\n\n---\n\n"
        "# The benchmark's own control reference\n\n"
        "The following is supplied by the environment you are running in and is "
        "authoritative for what the keys mean and how they behave. Where it describes a "
        "response format -- a single flat JSON object of keys -- that object is exactly "
        f"what goes in the `action` field of ONE entry of {actions_channel}; you still "
        "answer with `{\"actions\": [{\"action\": {...}, \"repeat\": N}, ...]}` as "
        "described above, and you do not emit its bare form.\n\n"
        f"{text}\n"
    )


#: `--minimal`: VISTA's bet -- a five-sentence prompt plus memory tools beat
#: a long rulebook on ARC-AGI-3. Ours keeps the task, the loop, the tools, the memory
#: line, one safety line and the procedure INDEX; every rule moves to references/ (as
#: `--thin` writes them) and the meta layer to skills/. Measured against two runs.
MINIMAL_CONTRACT = """\
You are an embodied agent playing Minecraft, controlling a player by writing action plans.

**Task**: {task_text}

{scoring_line}

{progress_block}

Reach as many milestones as you can within the step budget. Build and use a compact,
revisable model of this world and of your own state; update it as the evidence changes
what is supported.

**Each turn** the current view is attached and the turn message carries `[STATE]`,
`[INV]`, the ledger and the notes since your last plan. Reply with one line
`OBSERVED vs EXPECTED: ...` (did the last plan do what you predicted; what changed in
the view), then `[PLAN]` (2-3 sentences: what next, and what observation will show it
worked), then `EXPECT: ...` (what `[STATE]`, `[INV]`, `[EVENT]` and the view will show
if it works). Then write the file:
- `./actions.json` -- REQUIRED. `{{"actions": [...]}}`, see below.

{tools_line} is **deleted before your turn starts**: create it, do not edit it.

**Memory.** `./logs.txt` and `episodes/` are the complete record of this life
(`./tools/episodes.py --last N | --steps A B | --near X Z | --tag T | --grep text
[--sheet out.png] [--then-now <id>] --q "<question>"`);{previous_clause} `mine/` is yours
and is carried to your next life, and `mine/working.md` is put in front of you every turn. The log knows where; the frame
knows what: `view_image` a frame before you walk to a remembered place and, on arrival,
`./tools/episodes.py --then-now <that episode> --q "..."` once (this life's, or an earlier
life's under `previous/`); look after a hit, and when a plan's outcome surprised you.
{previous_note}
{safety_line}

{reference_head}
**Procedures** (name, arguments, one line each; full descriptions, preconditions and
the notes on each: `references/procedures.md`):
{procedures}
{atoms_line}
{references_tail}
"""

#: The same statement in the short contract of an arm without reflexes of its own.
THIN_SAFETY = ("**Safety.** The runner does not guard you in this run: no lava stop, no "
               "pillar on a hit, no refusal. Natural healing needs the food bar at 18+; here "
               "it falls about a point per 4000 steps, so a life's whole deficit is one animal "
               "(raw meat is fine) -- eat when the bar is below 18.")

_MINIMAL_SAFETY = {
    True: ("**Safety.** The runner has reflexes of its own -- lava coming into view, a "
           "fall, water under a dig, a hit, the Nether -- and when one stops your plan its "
           "`[NOTE]` says what it did and why. Read the note before you re-plan."),
    False: ("**Safety.** The runner does not guard you in this run: no lava stop, no "
            "pillar on a hit, no refusal. Your reflexes under `mine/reflexes/` are the tick "
            "layer, and none is installed for you: `skills/reflexes/SKILL.md` names the classes, "
            "`skills/reflexes/scripts/` holds examples to copy into `mine/reflexes/` in your "
            "first turn. Natural healing needs the food bar at 18+; here it falls about a point "
            "per 4000 steps, so a life's whole deficit is one animal (raw meat is fine) -- eat "
            "when the bar is below 18 (the starving example does it when you carry food)."),
}


def _previous_note() -> str:
    """The carried-lives paragraph every other mfm contract appends (mcu_worldmodel/previous.py):
    a pointer to previous/, not a digest -- the minimal contract went to one run
    without it and the model never opened previous/ in 24 turns."""
    from mcu_worldmodel.previous import MFM_PREVIOUS_NOTE
    return MFM_PREVIOUS_NOTE


def minimal_contract(*, task_text: str, progress_block: str, entry_cap: int, step_cap: int,
                     scored_by_milestones: bool = True, atoms: bool = False,
                     frames: bool = False, harness_reflexes: bool = True,
                     previous: bool = False, references_tail: str = "") -> str:
    head = ACTION_REFERENCE.split("**Procedures**")[0].format(
        actions_channel=_ACTIONS_CHANNEL["mfm"], entry_cap=entry_cap, step_cap=step_cap)
    if atoms:
        head = head.replace(_DIG_EXAMPLE, _ATOM_EXAMPLE)
    tools_line = _MFM_TOOLS_LINE.format(zoom=", a crop from `tools/zoom.py`" if frames else "")
    if not previous:                       # from scratch: no earlier life to look back at
        tools_line = tools_line.replace(" (this life's or an earlier life's under `previous/`)", "")
    return MINIMAL_CONTRACT.format(
        task_text=task_text,
        previous_clause=(" `previous/life_<i>/` the earlier lives in this same world;"
                         if previous else ""),
        previous_note=(("\n**Previous lives.** " + _previous_note() + "\nYour first turn is the "
                        "workshop turn (`skills/memory/SKILL.md`): read them before you play.\n")
                       if previous else ""),
        scoring_line=_SCORING_LINE[bool(scored_by_milestones)],
        progress_block=progress_block,
        tools_line=tools_line,
        safety_line=_MINIMAL_SAFETY[bool(harness_reflexes)],
        reference_head=head.rstrip() + "\n",
        procedures=P.index(),
        atoms_line=("\n" + _own_mod().atoms_line()) if atoms else "",
        references_tail=("\n" + references_tail.strip() + "\n") if references_tail.strip() else "",
    )


def action_reference(*, entry_cap: int, step_cap: int,
                     memory_mode: str = "mfm",
                     task_family: str = "from_scratch",
                     atoms: bool = False, harness_reflexes: bool = True,
                     own_reflexes: bool = False) -> str:
    """The shared action/perception reference, rendered for one memory mode.

    One function for all arms on purpose: everything except the explicitly per-mode
    substitutions is the same string object, which is what makes "shared substrate"
    checkable rather than aspirational."""
    ref = ACTION_REFERENCE.format(
        entry_cap=entry_cap, step_cap=step_cap,
        procedures=P.reference() + (("\n\n" + _own_mod().atoms_line()) if atoms else ""),
        recipes=G.reference(),
        actions_channel=_ACTIONS_CHANNEL[memory_mode],
        ground_truth_channels=_GROUND_TRUTH_CHANNELS[memory_mode],
        procedure_notes=_PROCEDURE_NOTES[memory_mode],
        skills_section=SKILLS_SECTION,
        chain_section=(_CHAIN_SECTION.format(strategy_bullets=_STRATEGY_BULLETS)
                       if task_family == "from_scratch" else ""),
        survival_rule=(_SURVIVAL_OWN.replace("{tick}", _SURVIVAL_TICK[bool(own_reflexes)])
                       if not harness_reflexes else
                       _SURVIVAL_RULE if task_family == "from_scratch"
                       else _SURVIVAL_GENERIC),
    )
    if atoms:
        ref = ref.replace(_DIG_EXAMPLE, _ATOM_EXAMPLE)
    # The procedures reference documents chop_tree's aim check as a zoom.py recipe, and
    # the ore-flag bullet points at a saved frame: the same advice in toolless wording.
    ref = ref.replace(
        "(zoom the frame centre to verify: ./tools/zoom.py <frame> 288 148 64 64)",
        "(look closely at the attached frame's centre to verify)")
    ref = ref.replace(
        "the [NOTE] names the file; zoom that one if in doubt",
        "the [NOTE] says so; look closely at the current view if in doubt")
    return ref


def act_prompt(*, task_text: str, progress_block: str, entry_cap: int,
               step_cap: int, platform_prompt: str = "",
               memory_mode: str = "mfm",
               task_family: str = "from_scratch",
               scored_by_milestones: bool = True,
               retrieval: bool = False,
               previous: bool = False, expect: bool = False,
               frames: bool = False, own: bool = False, atoms: bool = False,
               own_reflexes: bool = False,
               harness_reflexes: bool = True) -> str:
    contract = (_DIRECT_CONTRACT if memory_mode == "direct" else
                _mfm_contract(retrieval, previous, expect, frames, own,
                              own_reflexes, harness_reflexes=harness_reflexes))
    output_contract = (_DIRECT_OUTPUT_CONTRACT if memory_mode == "direct"
                       else "Then write these files:\n" + _OUTPUT_FILES[memory_mode])
    return ACT_PROMPT.format(
        task_text=task_text,
        scoring_line=_SCORING_LINE[bool(scored_by_milestones)],
        progress_block=progress_block,
        memory_contract=contract,
        # placeholders of the contract template that no arm fills; the template keeps
        # them so the blank lines of the recorded contracts stay where they were
        world_model_docs="",
        ground_truth_bullet=_GROUND_TRUTH_BULLET[memory_mode],
        belief_rules="", graph_section="", plan_section="", discipline_section="",
        plan_line=_PLAN_LINE[memory_mode],
        output_contract=output_contract,
        action_reference=(action_reference(entry_cap=entry_cap, step_cap=step_cap,
                                           memory_mode=memory_mode,
                                           task_family=task_family, atoms=atoms,
                                           harness_reflexes=harness_reflexes,
                                           own_reflexes=own_reflexes)
                          + platform_block(
                              platform_prompt,
                              "your actions JSON" if memory_mode == "direct"
                              else "your `actions.json`")),
    )
