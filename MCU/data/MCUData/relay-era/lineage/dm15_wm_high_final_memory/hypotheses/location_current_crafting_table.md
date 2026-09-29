# location_current_crafting_table

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2603
- updated_step: 9200
- depends_on: goal_crafting_table, location_shallow_stone_shaft, location_live_descent_1946, location_live_surface_table_1624, location_live_table_1813

## Statement

The this-run crafting table at block centre (-2998.5,64.5,-5563.5) is surface-reachable via the completed pillars and remained placed through step 9200.

## Evidence

- use_item crafting_table fired at 714; current-prefix events through 7200 contain no later mine_block or pickup crafting_table.
- use_item crafting_table fired at 714; no later mine_block/pickup crafting_table exists, and current position is about nine horizontal blocks away.
- The table GUI produced craft_item iron_pickaxe at 8008; the score is now 9/10 and the only unmet milestone is pickup diamond.
- Table use fired at 714 with no later break/pickup; nearby use_until_gui opened no screen at 10794.
- use_until_gui opened the table at step 3330 and enabled the step-3390 stone-pick craft. The step-3481 mine_ahead broke zero blocks, and no table mine/pickup event exists through 3600.
- STATE/map fix the pose; logs 5912-5917 record the exact target and GUI open=True; no later table break/pickup event exists.
- The table supported verified crafts; current events contain no later mine_block or pickup crafting_table.
- Step-8970 frame visibly shows the adjacent table after surface exit; no later mine/pickup event removes it.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
