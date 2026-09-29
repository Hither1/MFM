# goal_stone_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2261
- depends_on: goal_mine_cobblestone, goal_wooden_pickaxe, resource_current_cobblestone, location_current_crafting_table

## Statement

The stone_pickaxe milestone was verified at step 2194, and the crafted stone pickaxe is safely deposited in zero-based hotbar slot 5 by step 2261.

## Evidence

- At step 3934 the authoritative 3x3 GRID reports cells [0,1,2] occupied; inventory reports cobblestone x11 and sticks x2. The current slab output is expected from the incomplete top row and should change when the handle is placed.
- events/events.jsonl and the live harness report MILESTONE stone_pickaxe plus craft_item stone_pickaxe at step 3958; current cursor is landed over empty zero-based hotbar slot 6.
- No current stone_pickaxe event exists; 11,400 ticks remain and the recipe is established.
- No current craft_item stone_pickaxe exists; frame 1200 shows sticks x2 and cobblestone x7, with one additional uncollected drop.
- No current craft_item stone_pickaxe event exists through 1800; frame 1800 verifies sticks x2 and cobblestone x20.
- Step 2132 opened the table GUI; step 2138 state verifies cobblestone x12, sticks x2, and no craft event yet. The failed click was guard-aborted after the cursor reset between turns, without inventory loss.
- The live harness reports 5/10 and events/events.jsonl records MILESTONE stone_pickaxe plus craft_item stone_pickaxe +1 at step 2194. [CURSOR] is over hotbar slot 5 immediately after the output click.
- The live step-2261 inventory and hotbar explicitly report stone_pickaxe x1 in hotbar.6 after the step-2194 craft event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
