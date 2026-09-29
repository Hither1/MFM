# location_live_table_957

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 957
- updated_step: 1200
- depends_on: goal_crafting_table

## Statement

Refuted for the current prefix: no table placement occurred at step 957 near (-3006,69,-5567); this claim came from a future trajectory. The live table is the step-711 placement near (-3003,67,-5568).

## Evidence

- The placement action targeted (-3006.0,68.99,-5567.5); step 957 records crafting_table -1 and the current frame visibly centers the table from (-3005.87,70.17,-5565.61).
- Placement inventory decrement and use_item are verified at 957/961; no mine_block or pickup crafting_table exists through 1200.
- Current events at 957 contain dirt/wooden-pick activity, not crafting-table placement; the only current use_item crafting_table is at 714 after placement at 711.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
