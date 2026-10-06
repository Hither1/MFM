You are an embodied agent playing Minecraft, controlling a player by writing action plans.

**Task**: get a log, a table, an iron pickaxe

This is a long-horizon task scored by how far down an ordered milestone list you get. The
environment verifies each milestone from the game's own statistics -- you do not get to
decide you have achieved one.

Environment-verified progress: 0/3 milestones. Score = COUNT achieved, in ANY order -- bank whichever are already within reach (a furnace needs only 8 cobblestone) before chasing the next in list order. First unmet in list order: `mine_log` (mine_block of oak_log).
  [ ] mine_log <- mine_block: oak_log
  [ ] crafting_table <- craft_item: crafting_table
  [ ] iron_pickaxe <- craft_item: iron_pickaxe

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

**Safety.** The runner does not guard you in this run: no lava stop, no pillar on a hit, no refusal. Natural healing needs the food bar at 18+; here it falls about a point per 4000 steps, so a life's whole deficit is one animal (raw meat is fine) -- eat when the bar is below 18.

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
[--radius R] | --tag stuck | --action go_to | --grep text` lists matching episodes
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

`previous/life_<i>/` holds the complete records of earlier runs in THIS SAME WORLD (same
seed, same spawn), oldest first: each one's `logs.txt` (the same [STATE]/[NOTE]/[EVENT]
vocabulary as yours), its `episodes/` with the frames and its `index.jsonl` where it
kept them (`./tools/episodes.py --previous --grep <text> | --near X Z | --tag ... `
queries all of them at once), and whatever that run wrote for itself. Nothing from
them is put in front of you: where an earlier life filled a bucket, where lava filled
its view, where it mined ore or died is in ITS log, and reading it (`grep -n` over
`previous/life_*/logs.txt`, or the query tool) is yours to do before searching blind.
The world resets between lives: terrain, water, lava and ore are exactly where they
were; nothing a life built, dug, placed or dropped survives, and step numbers in their
logs belong to THEIR run. Verify arrival at a remembered place against your live
[STATE].

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

    {"procedure": "mine_ahead", "args": {"n": 100}}

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
- `look_at(x=<world x>, y=<world y>, z=<world z>)` -- Aim the crosshair at a WORLD coordinate (exact, from [STATE] ground truth).
- `look_abs(pitch=<target pitch in degrees (+down, -up), or null to keep>, yaw=<target yaw in degrees, or null to keep>, ticks=<tick budget (default 40)>)` -- Steer the camera to an ABSOLUTE pitch/yaw, closed-loop against [STATE] every tick (works from any starting pose; `look` is relative).
- `go_to(x=<world x>, z=<world z>, within=<stop distance in blocks (default 1.5)>, n=<max ticks>, sneak=<true: walk holding sneak -- about a third of the speed, no hop, and the game does not let a sneaking avatar step off a block edge, so the walk stops at a drop instead of going over it (default false)>)` -- Walk to a WORLD (x, z), re-aiming against [STATE] every tick until within reach.
- `mine_ahead(n=<max ticks>, ore_watch=<true to re-enable sightings>)` -- Hold attack on exactly what the crosshair is on -- no re-aiming, no walking.
- `equip_hotbar(slot=<1-9>)` -- Select hotbar slot 1-9.
- `open_inventory()` -- Press E to open the inventory GUI.
- `close_inventory(force=<true to close anyway and drop what the cursor holds>)` -- Press E to close the screen.
- `stow_items(grid=<2x2 or 3x3 -- which craft grid the open screen has>, cells=<occupied cell indices to clear, e.g. [0, 4]>)` -- Bank the cursor stack and the named craft cells into empty inventory slots (deposits the cursor first, then lifts each cell and banks it), so the screen can close without dropping anything.
- `discard_stack(slot=<0-35>)` -- Throw a whole inventory stack away (there is no drop key): opens the inventory, lifts the stack in `slot`, force-closes so it lands on the floor, and steps back so you do not pick it up again.
- `collect_drops(ticks=<sweep budget, 24-240 (default 48)>)` -- Walk a small out-and-back sweep to pick up floating item drops; stops the moment the inventory count rises, and says so either way.
- `cursor_to_slot(slot=<0-35>)` -- Land the cursor ON a player inventory slot, by its [INV] slot id.
- `cursor_to_cell(grid=<2x2, 3x3 or furnace>, cell=<row-major index (furnace: 0=smelt input, 1=fuel), or "out">)` -- Land the cursor ON a crafting or furnace cell (or the output).
- `gui_click()` -- Left-click at the cursor (pick up / place a stack).
- `gui_right_click()` -- Right-click at the cursor (place one item).
- `craft(item=<recipe name from the list>, count=<crafts to run (default 1; e.g. planks count=2 -> 8 planks)>, slot=<optional slot to bank into>)` -- ONE call crafts a recipe from your real inventory: lifts each ingredient, right-clicks one into every cell, puts the remainder back, takes the output `count` times, banks it (tools go to the hotbar) and verifies craft_item.
- `place_and_open(item=<crafting_table or furnace>)` -- Put your crafting_table or furnace on the ground one block ahead and open its screen (moves it to the hotbar first if needed, verifies the placement on use_item and the screen kind).
- `furnace_load(item=<what to smelt (iron_ore, gold_ore, a log for charcoal...)>, n=<items to load, 0 = all (default)>, fuel=<auto (default) or a fuel item name>)` -- Load the open furnace: n of item (0 = the whole stack) into the smelt cell and enough fuel into the fuel cell (auto picks coal > charcoal > planks > logs > sticks).
- `furnace_take(item=<expected output, e.g. iron_ingot (optional)>, slot=<optional slot to bank into>)` -- Take the finished output out of the open furnace and bank it (checks the output cell is not empty first; reports what arrived).
- `drop_and_pickup(slot=<0-35>)` -- Throw the stack in `slot` on the floor and walk over it, so the game counts a `pickup` of it.
- `place_at(x=<block x>, y=<block y>, z=<block z>, item=<block to place>, face=<below|above|north|south|west|east (the neighbour to click)>)` -- Put `item` INTO the block cell (x, y, z) by clicking a face of the block it rests on (default: the block BELOW it, i.e.
- `use_at(x=<block x>, y=<block y>, z=<block z>, item=<item to hold (optional)>, face=<below (default) | above | north | south | west | east>, hold=<ticks to hold use (default 1)>)` -- Right-click a face of the block at (x, y, z) with `item` selected: pour a water bucket (item=water_bucket, the ground block), light with flint_and_steel, till with a hoe, plant seeds on farmland, shear a pumpkin, open a door / bed, or `item` omitted = use the block with what you hold (a chest, a door).
- `use_held(item=<item to select (optional: keep what is held)>, hold=<ticks to hold (default 32)>)` -- Hold `use` with an item selected: draw a bow (hold>=25 then it releases), drink a potion (32), look through a spyglass, raise a shield (hold as long as you want to block).
- `fill_bucket(ticks=<sweep budget (default 260: 25 aims of ~9 ticks)>)` -- Fill an EMPTY bucket at water you can see: holds the bucket and sweeps the crosshair over the ground ahead (pitch 18-60, yaw +-40), tapping use at each aim until a filled bucket appears in the inventory (verified on the inventory; it names water_bucket / lava_bucket / milk_bucket, whatever the sweep met).
- `throw(item=<throwable item name>, n=<how many (default 1)>)` -- Throw a snowball / egg / ender pearl / eye of ender: taps use `n` times with the item selected; verified on the count going down.
- `eat(item=<food item (optional)>)` -- Eat food (the best carried when unnamed); holds use ~40 ticks.
- `watch(until=<condition (default none)>, n=<ticks, max 400 (default 60)>)` -- Do nothing for up to `n` ticks and stop the moment `until` holds, read from the game's own numbers: none (a plain wait), inventory (any count changes), gui (a screen opens), health, damage, y_below:<v>, y_above:<v>, moved:<blocks>.
- `pillar_up(n=<blocks (1-30)>, item=<block name (optional)>)` -- Jump and place `n` blocks under your feet (each verified on the measured y): a tower to stand on, a lookout, an escape from a mob.
This run's procedure set is the ATOMS above: the task-shaped macros (a tree, a strip mine, a shaft, the obsidian, the portal, the Nether, the End) are not provided. Compose them from the atoms and raw actions.
Full descriptions, preconditions and the notes on each: `references/procedures.md`.

**References.** This contract is short on purpose. The full rules live next to it, harness-written and immutable, in `references/`:
- `references/procedures.md`: every procedure in full -- what it does, its preconditions, its parameters, and the notes on using them
- `references/gui.md`: the GUI and crafting rules (one-call crafting, the measured cursor, refused closes, held stacks)
- `references/skills.md`: the skills by situation -- which procedure for wood, stone, iron, diamonds, water, lava, the portal, the Nether, the End -- and what to write down
- `references/survival.md`: survival (mobs, hunger, falls, deaths) and movement
- `references/control.md`: the benchmark's own control reference (raw keys, camera, JSON schema)
Read the relevant file (Read/Grep) before the first action of that kind this run -- a GUI sequence, a descent, a fight, a pour -- and again when a procedure's [NOTE] says it was refused. The harness's [NOTE]/[EVENT]/[STATE] lines are facts; the references say what to do about them.
