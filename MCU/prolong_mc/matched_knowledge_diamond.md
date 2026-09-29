The score is a COUNT of milestones, in ANY order -- bank whichever are within reach
before chasing the next in list order. The episode ends at step 12000 (each log
section's "Step M" header carries the current step); when fewer than ~800 steps
remain, stop exploring and bank the cheapest unmet milestone (a furnace is one
crafting-table visit with 8 cobblestone).

Recipes (2x2 = your inventory grid; 3x3 = a placed crafting table):
- planks x4 <- 1 log [2x2]; stick x4 <- 2 planks [2x2]; crafting_table <- 4 planks [2x2]
- wooden_pickaxe <- 3 planks + 2 sticks [3x3]; stone_pickaxe <- 3 cobblestone + 2 sticks [3x3]
- furnace <- 8 cobblestone [3x3]; iron_pickaxe <- 3 iron_ingots + 2 sticks [3x3]
- torch x4 <- 1 coal + 1 stick [2x2, coal above stick]

Facts that cost previous runs the game:
- `mine_cobblestone` counts breaking a COBBLESTONE block. Natural stone counts as
  `stone` (drops a cobblestone ITEM, no milestone). Place one cobblestone you hold and
  re-mine it (~30 ticks) for the guaranteed credit.
- Tools wear out: wooden tools have 59 uses, stone 131, iron 250. Craft the NEXT
  pickaxe before the current one breaks; keep 1 log (or 4 planks + 2 sticks) unspent
  at all times.
- Plan the wood trip once: ~3 logs from one tree cover the table, the pickaxe and a
  reserve.
- Plan the stone trip once: 3 cobblestone for the stone pickaxe AND 8 for the furnace;
  mine 11+ before leaving the stone face.
- A placed crafting table can be mined (~40 ticks) and carried; ONE table serves the
  whole run -- re-place it at each new base instead of walking back or spending 4 more
  planks.
- Iron ore needs at least a STONE pickaxe. In this Minecraft (1.16) iron spawns
  UNIFORMLY below y~63: start strip-mining as soon as you are underground; exposure
  (long tunnels, side branches) beats depth. Iron ore looks like grey stone with tan
  speckles. Go to y 12-20 only when diamonds are the target.
- Smelting: ore in the furnace's top cell, fuel (planks/coal) in the lower cell, ~200
  ticks per item, then TAKE the output -- the pickup is what the milestone counts.
- Right-clicking with a placeable block in hand PLACES the block instead of opening
  the screen you aim at: select a non-placeable item (a pickaxe) before opening.
- Never dig the block under your feet below y~40; descend on a staircase you can walk
  back up. If your health drops sharply, find the danger before resuming.
- Container screens auto-close when you drift out of reach (~5 blocks): stand ADJACENT
  to the table or furnace before opening. Never close a screen while items sit in the
  crafting grid or the cursor -- they drop on the floor.

The inventory GUI, measured against this build (the same facts the worldmodel arm's
prompt carries; the platform reference no longer documents them):
- `inventory` opens or closes the screen in ONE tick and is edge-triggered: press it
  for a single tick, then allow a tick or two before clicking into it.
- With the GUI open, `camera` moves the MOUSE CURSOR, not the head. The scale is
  4.17 pixels per degree, so one 18-pixel inventory slot is 4.32 degrees. A camera
  delta arrives as written, in one tick, at any magnitude (pitch clamps at +/-90).
- `attack` is left-click and `use` is right-click. Do NOT hold `attack` across
  consecutive ticks while the GUI is open -- that reads as click-and-drag and smears
  the stack across slots. One tick pressed, one tick released.
- To wield an item, select its hotbar slot with `hotbar.N`.
- Crafting is a closed loop: move a little, read the next frame plus the [GUI] and
  [INV] lines in your log, correct. Open-loop click macros do not work here. No [INV]
  change after a click means the click did nothing -- the picture alone is not proof.
