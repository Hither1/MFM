# location_current_crafting_table

- kind: location
- status: active
- confidence: 1.00
- created_step: 2603
- updated_step: 10800
- depends_on: goal_crafting_table, location_shallow_stone_shaft, location_live_descent_1946, location_live_surface_table_1624

## Statement

The this-run table should still occupy (-3003,67,-5569) and may aid rebuilding, but step 10794 failed to reacquire/open its face.

## Evidence

- use_item crafting_table fired at 714 and no later mine_block or pickup crafting_table exists through 4800.
- Use_item crafting_table at 714 is the only current table placement/use and no later mine/pickup table event exists.
- use_item crafting_table fired at 714; events through step 6000 contain no later mine_block or pickup crafting_table.
- use_item crafting_table fired at 714 and no later mine_block or pickup crafting_table exists through 6600.
- use_item crafting_table fired at 714; current-prefix events through 7200 contain no later mine_block or pickup crafting_table.
- use_item crafting_table fired at 714; no later mine_block/pickup crafting_table exists, and current position is about nine horizontal blocks away.
- The table GUI produced craft_item iron_pickaxe at 8008; the score is now 9/10 and the only unmet milestone is pickup diamond.
- Table use fired at 714 with no later break/pickup; nearby use_until_gui opened no screen at 10794.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
