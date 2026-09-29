# location_live_table_9440

- kind: location
- status: active
- confidence: 0.80
- created_step: 9555
- updated_step: 10800
- depends_on: goal_crafting_table, goal_iron_pickaxe

## Statement

The sole live crafting table remains overhead at the y44 worksite near (-2985.46,-5579.44), but its exact break ray is unresolved; the inferred center used at step 9561 aimed below it.

## Evidence

- Step 9437 place_block removed the carried table, step 9440 recorded use_item crafting_table, and use_until_gui reopened the table from the unchanged pose at step 9490.
- Table placement/use fired at 9437/9440 and no later table break/pickup exists. The 90-tick attack produced four stone breaks, while frame 9600 visibly shows the intact table above the crosshair.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
