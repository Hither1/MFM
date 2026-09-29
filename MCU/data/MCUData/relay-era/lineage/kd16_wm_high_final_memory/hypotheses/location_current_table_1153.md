# location_current_table_1153

- kind: location
- status: stale
- confidence: 1.00
- created_step: 1200
- updated_step: 4200
- depends_on: goal_crafting_table

## Statement

The original placed-table location is historical; the sole table was broken at step 4100 and is now carried after pickup at 4119.

## Evidence

- [INV] crafting_table -1 at step 1153 and use_item crafting_table at 1157 prove placement and access from the unchanged pose; ray geometry supplies the approximate block.
- [INV] crafting_table -1 at step 1153 and use_item crafting_table at 1157 prove placement/access; mine_ahead at step 1297 broke zero blocks and no later table pickup or break event exists.
- Current-reset break and pickup events resolve the formerly uncertain table ray and remove the world block.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
