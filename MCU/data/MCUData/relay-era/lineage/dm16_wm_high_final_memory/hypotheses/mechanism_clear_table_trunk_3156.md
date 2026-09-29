# mechanism_clear_table_trunk_3156

- kind: mechanism
- status: refuted
- confidence: 0.00
- created_step: 3156
- updated_step: 3600
- depends_on: location_current_crafting_table, location_table_west_2995, goal_crafting_table, location_table_east_detour_3314

## Statement

Refuted: mining the guessed trunk centre from the south face broke zero blocks in 110 ticks, and trunk removal was unnecessary because the east-side route opened the table.

## Evidence

- At step 2995 the ray to the stored table hit centered spruce bark from the reachable south pose; west detours at steps 3013-3156 repeatedly collided with vegetation and still failed to open the GUI, so removing the localized blocker is now the direct test.
- Step 3285 mine_ahead reports zero blocks; step 3367 GUI open=True with no intervening spruce-log event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
