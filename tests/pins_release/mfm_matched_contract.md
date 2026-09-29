You are an embodied agent playing Minecraft, controlling a player by writing action plans.

**Task**: get a log, a table, an iron pickaxe

This is a long-horizon task scored by how far down an ordered milestone list you get. The
environment verifies each milestone from the game's own statistics -- you do not get to
decide you have achieved one.

Environment-verified progress: 0/3 milestones. Score = COUNT achieved, in ANY order -- bank whichever are already within reach (a furnace needs only 8 cobblestone) before chasing the next in list order. First unmet in list order: `mine_log` (mine_block of oak_log).
  [ ] mine_log <- mine_block: oak_log
  [ ] crafting_table <- craft_item: crafting_table
  [ ] iron_pickaxe <- craft_item: iron_pickaxe

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

`episodes/` holds the same history as `logs.txt` a second time, structured: one
directory per plan entry (one procedure call or one held raw action -- exactly the
entries the log has an "Action N" section for). In each `ep_NNNNNN/`:
`observation/image.png` (the view the entry started from), `state/state.json`
(position, inventory, hotbar, GUI, vitals, mobs, milestones at the entry's first
tick), `action.json` (the entry, its place in the
plan, the briefing and plan it came from) and `outcome.json` (what it changed: moved,
descended, inventory delta, [EVENT]s, milestone transition, harness notes, tags such as
`stuck`, `inventory_changed`, `milestone`, `damage`, `gui`, `flushed`). `index.jsonl`
has one line per episode. `./tools/episodes.py --last 5 | --steps A B | --near X Z
[--radius R] | --tag stuck | --action dig_down | --grep text` lists matching episodes
one per line with their paths; add `--sheet out.png` to tile their frames into one
image you can view, `--json` for the rows. These files persist across turns like
`logs.txt`; they are harness-written and immutable.

**Look back.** The frames are for looking, not only for listing. Before you walk to a
remembered place, view the frame of the episode that stood there (`./tools/episodes.py
--near X Z`, then `view_image episodes/<id>/observation/image.png`; or `./tools/episodes.py
--then-now <id> --q "<what this look answers>"`, which writes that frame beside the
current view as `then_now.png`) so you recognise it on arrival; after a hit, the frame of the episode tagged `damage` (what hit you is in
it); when a plan has failed twice for a reason the numbers do not give, tile
its last entries' frames (`--sheet out.png`) and look at them together; before a route
over ground you have not walked, the frames of the nearest episodes; before a place from
an earlier life, that life's frame of it (`--previous --near X Z`). The log knows where;
the frame knows what.

When the episodes hold something that bears on this turn, the turn message carries a
`[RECALL]` block the harness computed from them: actions that have changed nothing in
their last several calls (and when the same action last did), what happened at this
spot earlier than the sections you can see. Each cited entry carries its frame path: when the one line is not enough,
`view_image` that frame -- what the entry saw is what you will see there -- or open the
episode (`./tools/episodes.py --steps A B`). Each cited place is given as a bearing and
a distance from where you stand. It is a reading of your own record, not advice, and it
is absent when there is nothing to recall.

**Expect, then compare.** End every briefing with one line `EXPECT: <what [STATE],
[INV] or [EVENT] will show if this plan works>`. The next turn opens with
`[EXPECTED]` (that line) and `[OBSERVED]` (what the harness recorded for the plan's
entries: moved, descended, inventory delta, events, the note it ended on). Begin the
briefing with `OBSERVED vs EXPECTED: ...` -- one sentence saying whether they match and
what differs -- before deciding anything. A plan whose expectation failed twice is not
re-proposed with the same target.

**Frames.** `./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]` crops a region of a
frame (640x360 pixels) and magnifies it 4x for `view_image`.
Each turn's second image is a 2x2 sheet of the frames at this turn's events (LAVA
AHEAD, a hit, a stalled walk, a failed re-open, a water refusal). Before opening a
frame, write the question it answers in one clause ("is the lava in the next cell or
two cells off?", "what stopped the walk at that note?"). The [STATE]/[NOTE] lines say
WHERE and THAT; the frame says WHAT. One look costs one image -- when a plan's outcome
surprised you, look before you re-plan.
Frames are FILES: a script (numpy and PIL are available) can read many of them and
answer one question over the whole set -- where the orange was, which frames show a
screen -- faster than viewing them one by one; `./tools/episodes.py --near X Z` lists
them by place with their paths.

Any other file or directory you create in `./` is removed when your turn ends; the
current view is attached to this call, and the earlier views are the episodes' images.
Whatever you will want to find again goes in your briefing and [PLAN], which the
harness writes into the log and into the episode.

**Tools**: Read, Bash, Grep, Glob to read the log and the episode index; `view_image <png>` to LOOK at a frame -- the attached view, any episode's `observation/image.png` (this life's or an earlier life's under `previous/`), a sheet from `--sheet`, a crop from `tools/zoom.py`; Write to create `actions.json`, which
is **deleted before your turn starts**. Create it; do not edit it. An edit is an update
to a file that is not there, it is rejected, and you spend the retry -- 77% of turns in
one run were paying for this.




**What you can rely on**:
- `[STATE]`'s yaw is CUMULATIVE, not wrapped: after enough turning it reads values like
  810 (= 810 - 720 = 90). Reduce it mod 360 before any heading arithmetic of your own;
  the closed-loop skills (look_abs, look_at, go_to) already handle it.
- Coordinates and facing in `[STATE]` are ground truth. Your read of a frame is not proof
  an action worked.
- The [EVENT] lines in `logs.txt` are ground truth. Your memory of what you crafted is not.





**Response format**: a short strategic briefing, then

[PLAN]
<2-3 sentences: what you are doing next and what observation will tell you it worked>

Then write these files:
- `./actions.json` -- REQUIRED. `{"actions": [...]}`, see below.

Each entry in `actions.json` is either a raw action held for N ticks:

    {"action": {"forward": 1, "sprint": 1}, "repeat": 30}

or a named procedure, which expands to many ticks:

    {"procedure": "dig_down", "args": {"n": 40}}

A list of at most 40 entries, totalling at most 50 environment ticks.

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
- `look(pitch=<degrees, + is down>, yaw=<degrees, + is right>)` -- Turn the camera by a relative (pitch, yaw) in degrees, in safe increments.
- `look_at(x=<world x>, y=<world y>, z=<world z>)` -- Aim the crosshair at a WORLD coordinate (exact, from [STATE] ground truth). Use for a block whose position you know: your placed table, a logged ore, a waypoint.  [A block's centre is corner + 0.5 per axis.]
- `look_abs(pitch=<target pitch in degrees (+down, -up), or null to keep>, yaw=<target yaw in degrees, or null to keep>, ticks=<tick budget (default 40)>)` -- Steer the camera to an ABSOLUTE pitch/yaw, closed-loop against [STATE] every tick (works from any starting pose; `look` is relative). Use look_at for a world point instead.
- `aim_at_ore(ticks=<tick budget (default 40)>)` -- Steer the crosshair onto the iron- or diamond-ore speckles the sentinel just flagged (closed loop on the live frame; stops centred or after 6 undetected frames). Follow with mine_ahead(n=120).  [Use right after an ore-stop [NOTE]; the speckles must still be on screen.]
- `aim_at_tree(ticks=<tick budget (default 40)>)` -- Steer the crosshair onto the most trunk-like bark column in view (closed loop on the live frame; stops centred or after 6 undetected frames). Follow with chop_tree; if chops then miss, walk 2-3 blocks forward while centred and chop again.  [A daylight scene with a tree (or its leaves) in view; useless underground and with a GUI open. It aims at the lower, choppable part of the trunk.]
- `use_until_gui(n=<max presses>, item=<crafting_table / furnace placed earlier by place_and_open: the runner aims at it for you>)` -- Right-click until a screen opens (checks the game each press). THE way to open a placed table or furnace; with item="crafting_table" (or "furnace") it first aims at where place_and_open put it.  [Aim at the block first (look_at), or pass item= for one this run placed. Select a NON-placeable hotbar item first (your pickaxe) -- right-click with a block in hand places the block instead of opening.]
- `go_to(x=<world x>, z=<world z>, within=<stop distance in blocks (default 1.5)>, n=<max ticks>)` -- Walk to a WORLD (x, z), re-aiming against [STATE] every tick until within reach. Use for any place whose coordinates you know: a tree you logged, your table, your shaft.  [Horizontal only -- it walks and hops but will not dig or climb more than a block.]
- `travel(n=<ticks, 1-200>, sprint=<true/false>)` -- Run forward in a straight line for n ticks (sprint + jump).  [Aim first with `look`; this does not turn. Prefer go_to when you know the destination's coordinates.]
- `harvest_tree(logs=<logs to collect (default 3; 4 covers the wooden phase)>, n=<tick budget, 60-1500 (default 500)>)` -- The wood loop, closed: centre the trunk in view, walk at it until it blocks you, chop until a log actually breaks, sweep the drop, repeat until `logs` logs are in the inventory. Breaks leaves in the way, jumps steps, and ends with a [NOTE] summary (logs collected / broken, empty chops). Use this for wood instead of aim_at_tree + chop_tree + walking by hand.  [A trunk (bark) must be on screen -- if the [NOTE] says no trunk was detected, walk toward visible LEAVES first, then run it again. Needs an empty hand or any tool; no screen open.]
- `chop_tree(n=<max ticks>, until_logs=<stop after this much wood (0 = never stop early)>)` -- Hold attack on the block you are aiming at (a trunk). Stops the moment wood breaks -- and also stops EARLY on a miss: after two non-wood breaks (you are on leaves) or 75 ticks of nothing breaking (out of reach / sky), with a [NOTE] saying which.  [Get within ~3 blocks of the trunk and centre a bark face (look closely at the attached frame's centre to verify). A miss-note means re-aim or approach, never just chop longer.]
- `mine_forward(n=<ticks>, ore_watch=<false to ignore ore sightings>)` -- Tunnel forward with verified movement: break the foot block, the eye block, walk into the opening, repeat. Ends with a [NOTE] reporting blocks broken and blocks ADVANCED; stops early (with a diagnosis) if it breaks blocks without gaining ground, and with a [NOTE] if iron- or diamond-ore-like speckles appear.  [Face the yaw you want the tunnel to run; the cycle sets its own pitch. To dig out ONE aimed block (after aim_at_ore), use mine_ahead instead.]
- `mine_ahead(n=<max ticks>, ore_watch=<true to re-enable sightings>)` -- Hold attack on exactly what the crosshair is on -- no re-aiming, no walking. THE follow-up to aim_at_ore: it digs out the aimed block without touching the camera.  [Aim first (aim_at_ore / look_at / look_abs).]
- `dig_down(n=<max ticks>, until_y=<stop once y <= this (12 is the mine level); omit for a fixed-tick dig>)` -- Aim straight down and mine the column under your feet, stopping at a target depth. The descent that has actually reached ore depth in every run that got there -- give it until_y and commit: 'dig to y=30' is one entry. The hazard is what opens below your feet (lava, caves, worst under y~40): watch the frames and the y readout, and stop at the first lava light.  [Never with lava below; check the y coordinate in [STATE].]
- `stair_down(depth=<blocks to descend>, ore_watch=<false to ignore ore sightings>)` -- Descend on a walkable staircase. No fall risk and a walkable way back up, but slow (~32 ticks per block) and it abandons entries on ground that will not take a stair -- the return trip and lava-shy stretches are its jobs; for reaching ore depth, dig_down with until_y is what has worked. Verifies its own descent and reports blocks broken / advanced / descended in a [NOTE].  [~32 ticks per block of depth. Sets its own pitch; face the yaw you want the staircase to run.]
- `strip_mine(length=<approx ticks>, ore_watch=<false to ignore ore sightings>)` -- Level tunnel with verified movement (same cycle as mine_forward). Ends with a broke/advanced [NOTE]; stops early with a diagnosis if it digs in place, and with a [NOTE] on an ore sighting.  [Run it at the mine level (y 11-12, after the one descent), torches in the hotbar; face the yaw you want.]
- `place_block()` -- Look down and right-click to place the held block.  [Select the block in the hotbar first with equip_hotbar.]
- `equip_hotbar(slot=<1-9>)` -- Select hotbar slot 1-9.
- `open_inventory()` -- Press E to open the inventory GUI.
- `close_inventory(force=<true to close anyway and drop what the cursor holds>)` -- Press E to close the screen.  [Refused (becomes a no-op + [NOTE]) while anything is off-inventory -- put it back in a slot first. [CURSOR] says what is off-inventory.]
- `stow_items(grid=<2x2 or 3x3 -- which craft grid the open screen has>, cells=<occupied cell indices to clear, e.g. [0, 4]>)` -- Bank the cursor stack and the named craft cells into empty inventory slots (deposits the cursor first, then lifts each cell and banks it), so the screen can close without dropping anything.  [A screen must be open. Name the occupied cells from [GRID]. Furnace slots never need this -- a furnace keeps its in/fuel/out contents when the screen closes.]
- `discard_stack(slot=<0-35>)` -- Throw a whole inventory stack away (there is no drop key): opens the inventory, lifts the stack in `slot`, force-closes so it lands on the floor, and steps back so you do not pick it up again. Use it to shed junk (dirt, gravel, granite/diorite/andesite, surplus cobblestone) when the Inventory line's free-slot count is low -- a full inventory silently loses every drop, including ore.  [No screen open; the slot id from [INV]/Hotbar (0-8 hotbar, 9-35 main rows). Ends facing the same way, two blocks back.]
- `collect_drops(ticks=<sweep budget, 24-240 (default 48)>)` -- Walk a small out-and-back sweep to pick up floating item drops; stops the moment the inventory count rises, and says so either way.  [Use it right after a break, at the spot that broke -- pickup needs you within ~1 block, and a sweep with no recent break nearby just spends its ticks. Drops can sit down the hole or behind the trunk.]
- `cursor_to_slot(slot=<0-35>)` -- Land the cursor ON a player inventory slot, by its [INV] slot id. Closed loop: steered against the pointer measured in each frame until it arrives. Prefer this over cursor_to.  [A screen must be open. 0-8 is the hotbar, 9-35 the three main rows.]
- `cursor_to_cell(grid=<2x2, 3x3 or furnace>, cell=<row-major index (furnace: 0=smelt input, 1=fuel), or "out">)` -- Land the cursor ON a crafting or furnace cell (or the output). Closed loop, like cursor_to_slot.  [The named grid's screen must be the one that is open.]
- `cursor_to(dx=<slots right>, dy=<slots down>)` -- Move the GUI cursor BY a slot offset. Relative -- use cursor_to_slot / cursor_to_cell when you know where you want to be.  [Only meaningful while a screen is open.]
- `gui_click()` -- Left-click at the cursor (pick up / place a stack).
- `gui_right_click()` -- Right-click at the cursor (place one item).
- `craft(item=<recipe name from the list>, count=<crafts to run (default 1; e.g. planks count=2 -> 8 planks)>, slot=<optional slot to bank into>)` -- ONE call crafts a recipe from your real inventory: lifts each ingredient, right-clicks one into every cell, puts the remainder back, takes the output `count` times, banks it (tools go to the hotbar) and verifies craft_item. Writes a [NOTE] either way; a failed craft drops the rest of the plan.  [The RIGHT screen must be open: open_inventory for a 2x2 recipe (planks, sticks, table, torch, flint_and_steel, blaze_powder, ender_eye), a crafting table's screen for a 3x3 one (pickaxes, swords, furnace, bucket). Ingredients per the recipe list.]
- `place_and_open(item=<crafting_table or furnace>)` -- Put your crafting_table or furnace on the ground one block ahead and open its screen (moves it to the hotbar first if needed, verifies the placement on use_item and the screen kind). Follow with craft / furnace_load.  [Carry the block; face flat ground with no screen open. To reopen a block already placed, use look_at(its coordinates) + use_until_gui.]
- `furnace_load(item=<what to smelt (iron_ore, gold_ore, a log for charcoal...)>, n=<items to load, 0 = all (default)>, fuel=<auto (default) or a fuel item name>)` -- Load the open furnace: n of item (0 = the whole stack) into the smelt cell and enough fuel into the fuel cell (auto picks coal > charcoal > planks > logs > sticks). Does not wait: ~200 ticks per item; close the screen and come back.  [The furnace screen must be open (place_and_open(item="furnace") or look_at + use_until_gui on a placed one).]
- `furnace_take(item=<expected output, e.g. iron_ingot (optional)>, slot=<optional slot to bank into>)` -- Take the finished output out of the open furnace and bank it (checks the output cell is not empty first; reports what arrived).  [The furnace screen must be open. Nothing to take before ~200 ticks per item have passed since loading.]
- `drop_and_pickup(slot=<0-35>)` -- Throw the stack in `slot` on the floor and walk over it, so the game counts a `pickup` of it. Needed when a milestone says `pickup X` and X came out of a furnace or a crafting grid (those count as craft_item, never pickup).  [No screen open; the slot id from [INV]. Clear ground ahead (the stack lands ~2 blocks in front of you).]
- `mine_until(item=<item name to wait for>, n=<how many more (default 1)>, ticks=<budget, 20-400 (default 240)>)` -- Hold attack on the block under the crosshair until n more of `item` are in the inventory (flint out of GRAVEL: ~1 block in 10; keep the crosshair on the gravel bank -- falling gravel refills the spot), or until the ticks run out.  [Aim first (look_at / look_abs); a pickaxe or shovel in hand.]
- `place_at(x=<block x>, y=<block y>, z=<block z>, item=<block to place>, face=<below|above|north|south|west|east (the neighbour to click)>)` -- Put `item` INTO the block cell (x, y, z) by clicking a face of the block it rests on (default: the block BELOW it, i.e. build on the ground / on the block under it; `face="north"` etc. attaches to that neighbour, e.g. a torch or an item frame on a wall). Aims from the live position, verifies on use_item, tries the nearest other face on a refusal, and says what happened.  [Within 4 blocks, not the cell you stand in, no screen open. Coordinates are block coordinates (floor of a position).]
- `use_at(x=<block x>, y=<block y>, z=<block z>, item=<item to hold (optional)>, face=<below (default) | above | north | south | west | east>, hold=<ticks to hold use (default 1)>)` -- Right-click a face of the block at (x, y, z) with `item` selected: pour a water bucket (item=water_bucket, the ground block), light with flint_and_steel, till with a hoe, plant seeds on farmland, shear a pumpkin, open a door / bed, or `item` omitted = use the block with what you hold (a chest, a door). Verified on use_item / the inventory / a screen opening.  [Within 4 blocks, no screen open. `face` = which side of the block to click (below = its top surface as seen from above).]
- `use_held(item=<item to select (optional: keep what is held)>, hold=<ticks to hold (default 32)>)` -- Hold `use` with an item selected: draw a bow (hold>=25 then it releases), drink a potion (32), look through a spyglass, raise a shield (hold as long as you want to block). Verified on use_item / the inventory.  [Aim first (look_at / face_entity) for a bow. No screen open.]
- `fill_bucket(ticks=<sweep budget (default 260: 25 aims of ~9 ticks)>)` -- Fill an EMPTY bucket at water you can see: holds the bucket and sweeps the crosshair over the ground ahead (pitch 18-60, yaw +-40), tapping use at each aim until a filled bucket appears in the inventory (verified on the inventory; it names water_bucket / lava_bucket / milk_bucket, whatever the sweep met). No coordinates or faces to guess, unlike use_at(bucket).  [An empty `bucket` carried; still water (a source block, not a stream) 1-3 blocks ahead and below the eye, within 4 blocks; no screen open.]
- `fetch_water(n=<tick budget for the search and walk (default 600; the plan's step cap shrinks it -- call it again to continue); the sweep at the shore adds up to 260>)` -- Get to water you can see and fill the bucket: looks around for the blue of still water (12 headings, if none is in view), walks toward it correcting the heading on every frame, breaks the leaves or dirt that stop the walk (a trunk is side-stepped), stops at the shore and runs fill_bucket there. The one call for a pond behind trees or across a clearing; go_to only walks to a coordinate and stops at the first obstacle.  [An empty `bucket` carried; still water (a pond, river or lake, not a stream's flow) visible from here or within a turn of the head; no screen open.]
- `throw(item=<throwable item name>, n=<how many (default 1)>)` -- Throw a snowball / egg / ender pearl / eye of ender: taps use `n` times with the item selected; verified on the count going down.  [Aim first; no screen open.]
- `eat(item=<food item (optional)>)` -- Eat food (the best carried when unnamed); holds use ~40 ticks. Only works while the food bar is below 20.
- `watch(until=<condition (default none)>, n=<ticks, max 400 (default 60)>)` -- Do nothing for up to `n` ticks and stop the moment `until` holds, read from the game's own numbers: none (a plain wait), inventory (any count changes), gui (a screen opens), health, damage, y_below:<v>, y_above:<v>, moved:<blocks>. The observe step between acting and deciding; ends with a [NOTE] saying what happened.
- `pillar_up(n=<blocks (1-30)>, item=<block name (optional)>)` -- Jump and place `n` blocks under your feet (each verified on the measured y): a tower to stand on, a lookout, an escape from a mob. Uses cobblestone/dirt/planks from the hotbar when `item` is omitted.  [Clear air above you; a placeable block carried.]
- `build_wall(item=<block>, length=<blocks wide (1-32)>, height=<1-6>, dist=<blocks ahead (1-3, default 2)>)` -- A wall `length` wide x `height` high, `dist` blocks AHEAD of you, running left-right across your facing (snapped to an axis), built from where you stand block by block with each placement verified; walks along the line for long walls. Reports placed / refused / not attempted, and resumes on a second call.  [Flat ground ahead; carry length x height blocks plus height-1 to stand on (each upper row is built from one block higher); face the wall's middle. Max height 6.]
- `build_row(item=<block>, length=<blocks (1-32)>)` -- A row of blocks on the ground running AWAY from you, from the block ahead: the far cells first, from where you stand, walking forward for the farther segments before they are built (a path, a fence line, a carpet strip).  [Flat, walkable ground along the row; carry `length` blocks.]
- `build_column(item=<block>, height=<1-6>, dist=<blocks ahead (default 2)>)` -- One column `height` high, `dist` blocks ahead of you (a pillar you look at, a snow golem body, a portal post).
- `bridge_forward(n=<blocks (1-32)>, item=<block (default cobblestone)>)` -- Extend the floor ahead `n` blocks over water / lava / a drop, stepping onto each placed block with sneak held (you cannot fall off). Faces snap to an axis.  [Stand at the edge facing the gap; carry n blocks.]
- `scan_around(steps=<4-12 (default 8)>, pitch=<camera pitch for the sweep (default 0; -20 looks slightly up for mountains/sky)>)` -- Turn a full circle in `steps` headings, saving a frame at each, and attach ONE contact sheet of them (yaw-labelled tiles) to your next turn -- the look-around for finding anything (a village, water, lava, sand, a tree line, a mob). Ends facing where you started.  [No screen open. Stand somewhere with a view (a hilltop, a pillar).]
- `sleep_in_bed(x=<bed block x>, y=<bed block y>, z=<bed block z>)` -- Right-click the bed at (x, y, z) and wait the night out (the bed screen opens; it closes when morning comes).  [Night time, within 3 blocks of the bed, no monsters near.]
- `explore_nether(axis=<x or z>, sign=<+1 or -1 (the direction along it)>, bearing=<a yaw in degrees to walk along instead of an axis (toward a sighting; optional)>, length=<blocks to cover, 8-200 (default 60; ~9 ticks per block)>, block=<block to bridge with (default: cobblestone, then netherrack)>)` -- Walk `length` blocks along one world axis IN THE NETHER looking for a fortress: keeps the heading, tunnels through netherrack when a wall stops you (eye block, foot block, walk), sneaks when lava fills the lower view and bridges an edge with your blocks, and STOPS the moment a nether-brick mass (a fortress) or a blaze is in view, saying the bearing. Reports blocks walked, tunnelled, bridged and where you are. Fortresses run along the x or z axis in long lines, so one leg per axis finds one where nothing else would; with `bearing` it walks along that yaw instead (toward a sighting).  [In the Nether, no screen open, a pickaxe carried (netherrack is soft) and 8+ cobblestone/netherrack for bridging lava.]
- `fight_blaze(ticks=<budget, 40-400 (default 300)>, retreat_hp=<back off at this health (default 6)>, weapon=<item to fight with (default: your best sword)>)` -- Melee a BLAZE to death with the blaze detector (in the Nether the plain fight mistakes lava for its yellow): faces it, walks in under it when swings miss, pulses attack, verifies kill_entity.blaze; then collect_drops for the rod.  [A blaze in view (explore_nether's note, or scan_around), a sword carried, health above 10 -- it shoots fire from range.]
- `enderman_pit()` -- Dig a 2-deep, 1x1 pit under your feet and look up at the rim: an enderman is three blocks tall and cannot hit what stands two blocks below its feet, while your sword reaches its legs. Then fight(label="enderman") from inside; after the kill, pillar_up(2) and collect_drops for the pearl.  [Solid ground (not over lava), a pickaxe carried, an enderman near (they wander the Nether's warped forests and the Overworld at night) but NOT yet angry -- look at it only from the pit.]
- `find_lava(n=<tick budget, 250-1500 (default 600, about 27 blocks of tunnel)>, y=<level to search at (default 11)>, leg=<blocks per straight leg before the 90-degree turn (default 40)>)` -- Find the lava the obsidian needs. Takes a staircase down to about y 11 if you are above it, then tunnels in straight legs (turning 90 degrees after each), watching the lower view for lava the whole way. STOPS the moment lava comes into view, at least 2 blocks short of it, and the note names the pool's cell, the RIM cell to pour from and the exact `make_obsidian(x, y, z)` call -- so a sighting turns into obsidian in one more step. Says how many blocks it searched and where to go next when it finds nothing.  [Underground (it is meant for y <= 15), a pickaxe carried, no screen open; carry the water_bucket so the pour can follow at once (fetch_water/fill_bucket first if you do not).]
- `make_obsidian(x=<rim block x (optional: with no x, y, z the last sighting's rim is used)>, y=<rim block y>, z=<rim block z>)` -- Turn lava into obsidian: pours a water bucket onto the TOP of the block at (x, y, z) -- a solid block at the edge of a lava pool -- waits for the flow to quench the lava sources, and scoops the water back (walking back into reach if the flow pushed you). With no x, y, z it pours on the last sighting's rim (find_lava's stop, or a LAVA AHEAD note with the bucket carried). Then mine_obsidian().  [Carry a water_bucket; stand 2-3 blocks from the pool on its rim, the rim block within 4 blocks. Flowing lava turns to cobblestone, only SOURCE blocks (still lava) become obsidian.]
- `mine_obsidian(x=<block x (optional: with no x, y, z the last sighting's pool cell)>, y=<block y>, z=<block z>, ticks=<budget, 240-400 (default 300)>)` -- Break the obsidian block at (x, y, z) with the diamond pickaxe: the aim is held on the block's centre every tick and the attack never released (about 190 ticks), stops the moment `mine_block obsidian` moves, then sweeps the drop. With no x, y, z it mines the last sighting's pool cell. Put it FIRST in its plan: it needs 240 ticks and is dropped whole when fewer are left.  [A diamond pickaxe carried; the block within 4 blocks.]
- `build_portal_frame(item=<obsidian>, dist=<blocks ahead (2-3)>)` -- Place the 14-obsidian outline of a nether portal (4 wide x 5 high, corners included) standing on the ground `dist` blocks ahead of you, across your facing; every block verified; call again to fill what was refused.  [14 obsidian (10 is the minimum frame; this places the corners too so each block has a neighbour to build on); flat ground ahead; stand 2 blocks back from the line, facing it.]
- `light_portal(dist=<the dist the frame was built with>)` -- Light the frame built by build_portal_frame from the same spot: flint_and_steel on the inside of its bottom row; checks the purple appears.  [Same position and facing as build_portal_frame; flint_and_steel carried.]
- `enter_portal(dist=<the dist the frame was built with>, x=<portal cell x (optional)>, z=<portal cell z (optional)>)` -- Walk into the lit portal (the frame built from this spot, or the cell at x, z) and stand until the dimension changes; reports where you arrived.  [The portal is lit (light_portal's note). Takes ~4 s in the purple; the trip back is the same call from the other side.]
- `container_take(items=<"all" (default) or a comma-separated list you are looking for>, max_stacks=<cells to empty in this call (default 27; a double chest has 54, so call it twice)>)` -- Empty the open chest, barrel or double chest into your inventory in ONE call: reads which cells hold something from the frame, quick-moves each of them, and reports what arrived and how many cells are left. Says so and stops when the chest is empty or your inventory is full.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. A chest cell does not say WHAT is in it, only that it is full, so `items` filters the report, not the taking.]
- `container_put(item=<item name from [INV]>, n=<items to move, 0 = all (default)>)` -- Move an item from your inventory into the open chest and verify it left your inventory. n=0 quick-moves every stack you carry; a smaller n puts exactly that many into one empty cell.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. A chest keeps its contents across a close.]
- `brew(ingredient=<nether_wart, magma_cream, blaze_powder, sugar, glistering_melon_slice... (default nether_wart)>, bottles=<bottles to load from your inventory, 0-3 (default 3; 0 when they are already in the stand)>, fuel=<blaze_powder (default) or none>)` -- Load the open brewing stand in ONE call: potions/water bottles into the three bottle cells, blaze powder into the fuel cell, one ingredient into the ingredient cell, verified against the inventory and the [GRID] row. It does NOT wait -- a brew takes 400 ticks and runs with the screen closed.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. Fire resistance is two brews: water bottles + nether_wart (-> awkward), then + magma_cream, 400 ticks each. Call brew(bottles=0) for the second one, the bottles are already in the stand.]
- `brew_take()` -- Take the three bottles out of the open brewing stand and report what arrived. Every potion reads as `potion` in the inventory -- the harness cannot name which one, only count them.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. Nothing has finished before 400 ticks per ingredient have passed since brew().]
- `enchant(item=<what to enchant, e.g. diamond_sword (default)>, option=<which of the three offers, 1-3 (default 1)>)` -- Enchant an item at the open enchanting table in ONE call: the item and your lapis in, option button 1-3 clicked, the item and the leftover lapis taken back out. Verified on the lapis spent -- the inventory observation carries no NBT, so that is the only channel that says the enchantment applied.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. Option N costs N lapis_lazuli AND N experience levels; with no levels the click does nothing and the macro says so.]
- `stonecut(item=<what to cut, e.g. stone (default)>, output=<what you want out, e.g. stone_bricks (drives the search)>, button=<recipe button 0-11 to click directly (default -1 = search). Measured for stone: 0 chiseled_stone_bricks, 1 stone_brick_slab, 2 stone_brick_stairs, 3 stone_brick_wall>, tries=<buttons to try when searching (default 4)>)` -- Cut a block at the open stonecutter into another and take the result. The recipe buttons are icons the harness cannot read, so it clicks them in order and reports what each produced until `output` arrives; the note names the button that worked so the next call can pass it directly.  [The container's screen must already be open: stand within ~4 blocks, equip_hotbar a NON-PLACEABLE item (a pickaxe, a torch -- a block in hand gets placed instead), look_at the block's exact x/y/z, then use_until_gui. Each attempt consumes one input item. A stonecutter offers only the recipes valid for its input; [GRID] counts how many buttons are drawn.]
- `face_entity(ticks=<budget, 10-200 (default 60)>, label=<mob name to look for (optional but recommended)>)` -- Turn the crosshair onto the nearest ENTITY in view and stop when it is centred: a mob (it is found by the motion it makes against a still world, and by its colour), a boat, an animal. This is the aim step every other entity action needs -- there is no entity channel in the observation, so a mob has no coordinate you can look_at. `label` (zombie, skeleton, spider, creeper, enderman, pig, cow, sheep, chicken, wolf, witch, blaze, phantom, or boat) narrows the colour search and makes it much more reliable. Says what it found and where you now face; says 'nothing in view' when there is nothing, and then you should scan_around or turn.  [No screen open. The entity must be somewhere in the current view (roughly +-50 degrees); turn first if it is behind you.]
- `fight(ticks=<budget, 40-400 (default 300)>, retreat_hp=<back off at this health (default 6)>, weapon=<item to fight with (default: your best sword/axe)>, label=<mob name to look for (optional)>)` -- Melee an entity to death: selects your best sword (or the weapon you name), faces the target, walks in when the swings are not landing, and PULSES attack on the sword cooldown until it dies. Reports swings, hits landed (use_item.<weapon>), damage dealt, the kill (kill_entity) and the health you lost. Stops early and says so on: the kill, the target leaving view, or your health falling to `retreat_hp` (it backs off ~3 blocks first). Against a SKELETON close the distance fast before you start -- it out-ranges you; against a creeper hit and step back; a spider is fast and low, aim down.  [No screen open, the mob in front of you (call face_entity first if it is not), and a weapon carried (bare hands work but take three times as long). Eat first if health is low.]
- `shoot_bow(shots=<arrows to fire, 1-10 (default 3)>, draw=<draw ticks, 25-60 (default 25; a full draw is 25)>, label=<mob name to look for (optional)>)` -- Shoot arrows at an entity: faces it, holds the draw >= 25 ticks, releases, re-faces, `shots` times. Verified on use_item.bow and the arrow count; the note reports the damage dealt and any kill. The right tool for a phantom overhead, a skeleton across a gap, or softening a mob before melee.  [A bow AND arrows carried, no screen open, the target in view. Arrows drop over distance -- past ~10 blocks aim above it.]
- `block_with_shield(ticks=<how long to hold the block, 10-200 (default 60)>)` -- Raise your shield for `ticks` and report the health you lost while it was up. A raised shield only covers the direction you FACE and you cannot attack while it is up, so the pattern is: face_entity, block through its swing, then fight.  [A shield carried (the macro moves it to the hotbar itself), no screen open, facing the attacker.]
- `use_on_entity(item=<item to use (shears, bucket, lead, wheat, fishing_rod, oak_boat...; omit to use what you hold)>, ticks=<budget, 20-200 (default 60)>, label=<mob name to look for (optional)>)` -- Right-click an ENTITY with an item: shears on a sheep (wool), a bucket on a cow (milk), a lead on any animal, food to feed/breed it, a fishing rod cast at it, or `oak_boat` on a boat floating in front of you to GET IN. Faces it first, clicks, and retries with a slightly different aim up to three times; verified on the inventory, use_item, or your position jumping (that is you boarding). Says which of those moved.  [Within 3 blocks of the entity (entity reach is shorter than block reach), no screen open, the item carried.]
- `boat_forward(ticks=<10-400 (default 60)>, yaw=<absolute heading to steer onto first (optional; 0 = +z, 90 = -x, -90 = +x)>)` -- Drive the boat you are sitting in: hold forward for `ticks`, optionally after turning to an absolute heading. Reports how far you actually moved -- if that is under a block you are not in the boat, or it is aground (a boat only moves on water or ice).  [You are IN the boat (use_on_entity(item='oak_boat') first) and there is open water ahead.]
- `leave_boat(ticks=<sneak ticks (default 12)>)` -- Get out of the boat (sneak), verified on your y rising back out of the hull.
- `throw_eye(fetch=<true to walk out along the bearing looking for a dropped eye (default false)>)` -- Throw an eye of ender and WATCH it: reports the yaw it flew toward (the stronghold's bearing) and whether it climbed (far) or dropped (the stronghold is below you). Each throw uses the eye up (it does not drop back here).  [Stand in the open with a clear view ahead (the eye flies up to 12 blocks); ender_eye carried; no screen open.]
- `travel_bearing(yaw=<heading in degrees (from throw_eye)>, blocks=<distance (2-400)>)` -- Walk `blocks` along the world heading `yaw` in closed-loop legs (jumping small rises), and say how far you got; stops early at a wall, a drop or lava.  [Overland walking; long trips are several calls.]
- `fill_end_portal(x=<pit centre x>, y=<frame level y>, z=<pit centre z>)` -- Put an eye of ender into every empty frame of the End portal: the 12 frames stand around a 3x3 pit; (x, y, z) is the pit's middle cell at the FRAMES' level. Walks around the ring outside it, clicks each frame's outer face with an eye, verifies each on the eye count; a frame that refuses already holds one. Resumable.  [Standing in the portal room, 1-12 ender_eye carried (one per empty frame), no screen open.]
- `enter_end(x=<pit centre x>, y=<frame level y>, z=<pit centre z>)` -- Jump into the activated End portal (the pit centred on x, y, z) and wait for the teleport; reports the End and where the island lies.  [All 12 frames hold an eye (the pit shows the black starry portal).]
- `mine_end_stone(yaw=<heading (optional, default toward the island)>, pitch=<camera pitch, + is down (default 30)>, ticks=<budget (default 240)>)` -- Dig the pale End ground with a pickaxe until an end_stone is picked up: aims at pitch `pitch` toward the island (x 0, z 0) or the given `yaw`.  [In the End, a pickaxe carried, end stone within reach in that direction (the spawn platform itself is obsidian).]
- `break_crystal(shots=<arrows to spend (default 3)>, ticks=<budget (default 300)>)` -- Destroy the end crystal in view (the bright magenta/white cube on top of an obsidian tower): draws and shoots the bow at it up to `shots` times, or hits it when no bow is carried (it explodes -- keep 3+ blocks away). Verified by the crystal vanishing from the view.  [The crystal in view (look up at a tower); bow + arrows for safety.]
- `attack_dragon(ticks=<budget (60-400)>, retreat_hp=<health to back off at (default 6)>, weapon=<item to hold (optional)>)` -- Melee the ender dragon while it is in reach -- it perches on the bedrock fountain at the island's centre between flights: finds the black mass, closes in, pulses the sword, backs off at `retreat_hp`. Verified on damage_dealt / kill_entity.  [Crystals broken first (they heal it); stand by the fountain when it lands; a sword carried.]

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
  `look_at(its coordinates)` then `use_until_gui` (or `use_until_gui(item="crafting_table")`,
  which aims at where place_and_open put it), with a NON-placeable item selected
  (your pickaxe) -- right-clicking with a block in hand places the block instead.
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
3. The [INV] and [EVENT] lines in `logs.txt` are the ground truth
   for what a click did: **no [INV] line and no `craft_item`/`pickup` event means the
   click changed nothing**. The frame is not proof: it lags a tick and does not show what
   the cursor is holding.
4. The **[GRID]** line reads the frame at every grid slot's known position and lists the
   ones that visibly hold an item; read only your open screen's row. Leftovers in cells
   are retrieved with `stow_items(grid=..., cells=[...])` (banks the cursor stack too).

**A close that would drop items is refused.** Closing a screen while something is
off-inventory throws it on the floor -- it cost a previous run four of its five logs -- so
the runner turns that toggle into a no-op and writes a [NOTE]. Put the stack back in a
slot (`stow_items`), then close. If you *mean* to drop it, `{"procedure":
"close_inventory", "args": {"force": true}}`. A furnace KEEPS its cells across a close.

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
  on top. A nether portal is an obsidian frame 4 wide x 5 high standing on the ground (10
  obsidian without the corners: two columns of 3 above two floor blocks, two blocks across
  the top) lit with `use_at(..., item="flint_and_steel")` on a floor block inside the frame.
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
  crafting table opens with `look_at(its block centre)` + `use_until_gui`, holding a NON-
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
  it, at your feet level) so it can be reopened later with `look_at` + `use_until_gui`
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
  blocker for the descent, the same way "no pickaxe" blocks mining.
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
  base instead of spending 4 planks on a fresh one.
- **Smelting**: `place_and_open(item="furnace")` at the mine face, `furnace_load(
  item="iron_ore")` (the whole stack, auto fuel), `close_inventory`, keep mining, and on
  the next pass `look_at` the furnace + `use_until_gui` + `furnace_take(item=
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

Recipes available:
- `planks` (x4) <- 1x logs  [inventory 2x2]
- `stick` (x4) <- 2x planks  [inventory 2x2]
- `crafting_table` (x1) <- 4x planks  [inventory 2x2]
- `wooden_pickaxe` (x1) <- 3x planks, 2x stick  [crafting table 3x3]
- `stone_pickaxe` (x1) <- 3x cobblestone, 2x stick  [crafting table 3x3]
- `iron_pickaxe` (x1) <- 3x iron_ingot, 2x stick  [crafting table 3x3]
- `diamond_pickaxe` (x1) <- 3x diamond, 2x stick  [crafting table 3x3]
- `stone_sword` (x1) <- 2x cobblestone, 1x stick  [crafting table 3x3]
- `iron_sword` (x1) <- 2x iron_ingot, 1x stick  [crafting table 3x3]
- `diamond_sword` (x1) <- 2x diamond, 1x stick  [crafting table 3x3]
- `furnace` (x1) <- 8x cobblestone  [crafting table 3x3]
- `flint_and_steel` (x1) <- 1x iron_ingot, 1x flint  [inventory 2x2]
- `blaze_powder` (x2) <- 1x blaze_rod  [inventory 2x2]
- `ender_eye` (x1) <- 1x blaze_powder, 1x ender_pearl  [inventory 2x2]
- `torch` (x4) <- 1x coal, 1x stick  [inventory 2x2]
- `bucket` (x1) <- 3x iron_ingot  [crafting table 3x3]
- `charcoal_torch` (x4) <- 1x charcoal, 1x stick  [inventory 2x2]
- `wooden_axe` (x1) <- 3x planks, 2x stick  [crafting table 3x3]
- `wooden_shovel` (x1) <- 1x planks, 2x stick  [crafting table 3x3]
- `wooden_hoe` (x1) <- 2x planks, 2x stick  [crafting table 3x3]
- `wooden_sword` (x1) <- 2x planks, 1x stick  [crafting table 3x3]
- `stone_axe` (x1) <- 3x cobblestone, 2x stick  [crafting table 3x3]
- `stone_shovel` (x1) <- 1x cobblestone, 2x stick  [crafting table 3x3]
- `stone_hoe` (x1) <- 2x cobblestone, 2x stick  [crafting table 3x3]
- `iron_axe` (x1) <- 3x iron_ingot, 2x stick  [crafting table 3x3]
- `iron_shovel` (x1) <- 1x iron_ingot, 2x stick  [crafting table 3x3]
- `iron_hoe` (x1) <- 2x iron_ingot, 2x stick  [crafting table 3x3]
- `golden_axe` (x1) <- 3x gold_ingot, 2x stick  [crafting table 3x3]
- `golden_shovel` (x1) <- 1x gold_ingot, 2x stick  [crafting table 3x3]
- `golden_hoe` (x1) <- 2x gold_ingot, 2x stick  [crafting table 3x3]
- `golden_pickaxe` (x1) <- 3x gold_ingot, 2x stick  [crafting table 3x3]
- `golden_sword` (x1) <- 2x gold_ingot, 1x stick  [crafting table 3x3]
- `diamond_axe` (x1) <- 3x diamond, 2x stick  [crafting table 3x3]
- `diamond_shovel` (x1) <- 1x diamond, 2x stick  [crafting table 3x3]
- `diamond_hoe` (x1) <- 2x diamond, 2x stick  [crafting table 3x3]
- `ladder` (x3) <- 7x stick  [crafting table 3x3]
- `chest` (x1) <- 8x planks  [crafting table 3x3]
- `door` (x3) <- 6x planks  [crafting table 3x3]
- `fence` (x3) <- 4x planks, 2x stick  [crafting table 3x3]
- `fence_gate` (x1) <- 4x stick, 2x planks  [crafting table 3x3]
- `boat` (x1) <- 5x planks  [crafting table 3x3]
- `bookshelf` (x1) <- 6x planks, 3x book  [crafting table 3x3]
- `bed` (x1) <- 3x wool, 3x planks  [crafting table 3x3]
- `carpet` (x3) <- 2x wool  [inventory 2x2]
- `glass_pane` (x16) <- 6x glass  [crafting table 3x3]
- `item_frame` (x1) <- 8x stick, 1x leather  [crafting table 3x3]
- `painting` (x1) <- 8x stick, 1x wool  [crafting table 3x3]
- `stonecutter` (x1) <- 1x iron_ingot, 3x stone  [crafting table 3x3]
- `enchanting_table` (x1) <- 1x book, 2x diamond, 4x obsidian  [crafting table 3x3]
- `clock` (x1) <- 4x gold_ingot, 1x redstone  [crafting table 3x3]
- `compass` (x1) <- 4x iron_ingot, 1x redstone  [crafting table 3x3]
- `diorite` (x2) <- 2x quartz, 2x cobblestone  [inventory 2x2]
- `cake` (x1) <- 3x milk_bucket, 2x sugar, 1x egg, 3x wheat  [crafting table 3x3]
- `bread` (x1) <- 3x wheat  [crafting table 3x3]
- `sugar` (x1) <- 1x sugar_cane  [inventory 2x2]
- `paper` (x3) <- 3x sugar_cane  [crafting table 3x3]
- `book` (x1) <- 3x paper, 1x leather  [inventory 2x2]
- `shears` (x1) <- 2x iron_ingot  [inventory 2x2]
- `bow` (x1) <- 3x stick, 3x string  [crafting table 3x3]
- `arrow` (x4) <- 1x flint, 1x stick, 1x feather  [crafting table 3x3]
- `fishing_rod` (x1) <- 3x stick, 2x string  [crafting table 3x3]
- `lead` (x2) <- 4x string, 1x slime_ball  [crafting table 3x3]
- `shield` (x1) <- 6x planks, 1x iron_ingot  [crafting table 3x3]
- `snow_block` (x1) <- 4x snowball  [inventory 2x2]
- `jack_o_lantern` (x1) <- 1x carved_pumpkin, 1x torch  [inventory 2x2]
- `beehive` (x1) <- 6x planks, 3x honeycomb  [crafting table 3x3]
- `iron_bars` (x16) <- 6x iron_ingot  [crafting table 3x3]
- `iron_helmet` (x1) <- 5x iron_ingot  [crafting table 3x3]
- `iron_chestplate` (x1) <- 8x iron_ingot  [crafting table 3x3]
- `iron_leggings` (x1) <- 7x iron_ingot  [crafting table 3x3]
- `iron_boots` (x1) <- 4x iron_ingot  [crafting table 3x3]
- `stone_bricks` (x4) <- 4x stone  [inventory 2x2]
- `smooth_stone_slab` (x6) <- 3x smooth_stone  [crafting table 3x3]
- `cobblestone_slab` (x6) <- 3x cobblestone  [crafting table 3x3]
- `stone_brick_slab` (x6) <- 3x stone_bricks  [crafting table 3x3]
- `cobblestone_stairs` (x4) <- 6x cobblestone  [crafting table 3x3]
- `lantern` (x1) <- 8x iron_nugget, 1x torch  [crafting table 3x3]
- `glass_bottle` (x3) <- 3x glass  [crafting table 3x3]
- `brewing_stand` (x1) <- 1x blaze_rod, 3x cobblestone  [crafting table 3x3]
- `iron_nugget` (x9) <- 1x iron_ingot  [inventory 2x2]
- `gold_nugget` (x9) <- 1x gold_ingot  [inventory 2x2]
- `flower_pot` (x1) <- 3x brick  [crafting table 3x3]
- `smoker` (x1) <- 4x logs, 1x furnace  [crafting table 3x3]

**Write down what worked.** The moment a GUI sequence lands -- a recipe crafted, an item
moved where you wanted it -- put it in your briefing before the detail is gone: the
harness writes your briefing and [PLAN] into `logs.txt`, and that is the only place it
survives. Not a summary of the recipe layout; what goes in is the part you cannot
re-derive from a picture:

    # iron at the face (one visit, no climbing)
    Preconditions: 3+ iron_ore, 8 cobblestone, 4 planks, 2 sticks; stone pickaxe held.
    1. place_and_open(item="furnace"), furnace_load(item="iron_ore") -> [NOTE] "3 in
       the smelt cell, 2 planks in the fuel cell"; close_inventory; strip_mine 600 ticks
    2. look_at(furnace x+0.5, y+0.5, z+0.5), use_until_gui, furnace_take(item="iron_ingot")
    3. place_and_open(item="crafting_table"), craft(item="iron_pickaxe"), close_inventory
    Failure seen: place_and_open on a slope put the table out of reach -- flat ground first.

Address slots and cells by number, not by offset. Grep the log for your own earlier
briefings before crafting anything a second time. This is the difference between solving
a recipe once and solving it every time.

**Survival** (a previous run died twice and lost everything):
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
  the way you came and wall it off. While hits keep coming, a plan that MOVES you
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
  pillar or the turn, never a sprint.
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


---

# The benchmark's own control reference

The following is supplied by the environment you are running in and is authoritative for what the keys mean and how they behave. Where it describes a response format -- a single flat JSON object of keys -- that object is exactly what goes in the `action` field of ONE entry of your `actions.json`; you still answer with `{"actions": [{"action": {...}, "repeat": N}, ...]}` as described above, and you do not emit its bare form.

HOST REFERENCE

