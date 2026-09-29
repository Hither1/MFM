# goal_stone_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 3390
- depends_on: goal_mine_cobblestone, goal_wooden_pickaxe, resource_current_cobblestone, location_current_crafting_table, location_live_table_1813

## Statement

The live stone_pickaxe milestone was environment-verified at step 3390 when the completed table output was taken onto the cursor.

## Evidence

- The live harness reports 5/10 and events/events.jsonl records MILESTONE stone_pickaxe plus craft_item stone_pickaxe +1 at step 2194. [CURSOR] is over hotbar slot 5 immediately after the output click.
- The live step-2261 inventory and hotbar explicitly report stone_pickaxe x1 in hotbar.6 after the step-2194 craft event.
- No current stone-pickaxe craft event exists.
- No craft_item stone_pickaxe exists through step 3000; events/frame verify the current inputs and table evidence remains unchanged.
- Step-3149 STATE verifies cobblestone x6 and sticks x2 with no current craft_item stone_pickaxe event; table use was verified at step 2181.
- Steps 3240-3256 completed the pitch-88 pillar ascent to y64, steps 3278-3317 reached the table, and step 3330 opened its GUI. Step 3336 STATE reports cobblestone x4 and sticks x2 with the table GUI still open.
- At step 3371, [INV] stick -2 proves the stick stack was lifted; active [GRID] shows 3x3 cells [0,1,2] occupied and out=FULL only for the temporary slab layout. The cursor aggregate names cobblestone x3 in-grid and stick x2 on-cursor.
- events/events.jsonl records MILESTONE stone_pickaxe and craft_item stone_pickaxe +1 at live step 3390; the harness score is 5/10.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
