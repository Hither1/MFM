# location_live_table_2077

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2077
- updated_step: 4633
- depends_on: goal_crafting_table

## Statement

The current-reset crafting table remains beside the original surface worksite; from (-2998.91,64.00,-5563.32), the exact placement ray pitch +25/yaw -103 reopened its 3x3 GUI at step 4633.

## Evidence

- Action 125 at step 2077 records place_block with [INV] crafting_table -1 and no player movement; the attached frame visibly fills the center with the crafting-table face.
- Step 2077 records crafting_table -1 on placement, and the table GUI stayed open at the unchanged pose through the verified wooden-pickaxe craft and banking at step 2152.
- At step 4628 look_abs reached pitch 25/yaw -103 from the original placement area; use_until_gui then changed GUI open from false to true at step 4633.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
