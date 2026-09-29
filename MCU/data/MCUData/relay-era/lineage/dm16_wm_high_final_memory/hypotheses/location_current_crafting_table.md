# location_current_crafting_table

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2603
- updated_step: 3600
- depends_on: goal_crafting_table, location_shallow_stone_shaft, location_live_descent_1946, location_live_surface_table_1624, location_live_table_1813

## Statement

The this-run crafting table remains placed at block centre (-3007.5,69.5,-5566.5), adjacent to the current player and the newly placed furnace; its GUI last opened from the east pose at step 3367.

## Evidence

- The table GUI produced craft_item iron_pickaxe at 8008; the score is now 9/10 and the only unmet milestone is pickup diamond.
- Table use fired at 714 with no later break/pickup; nearby use_until_gui opened no screen at 10794.
- use_until_gui opened the table at step 3330 and enabled the step-3390 stone-pick craft. The step-3481 mine_ahead broke zero blocks, and no table mine/pickup event exists through 3600.
- STATE/map fix the pose; logs 5912-5917 record the exact target and GUI open=True; no later table break/pickup event exists.
- The table supported verified crafts; current events contain no later mine_block or pickup crafting_table.
- Step-8970 frame visibly shows the adjacent table after surface exit; no later mine/pickup event removes it.
- placement targeted this centre; table INV -1/use_item fired at 1256 and no later mine_block or pickup crafting_table event exists.
- No table mine/pickup follows placement; GUI open=True at 3367 and frame 3600 shows the table beside the furnace.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
