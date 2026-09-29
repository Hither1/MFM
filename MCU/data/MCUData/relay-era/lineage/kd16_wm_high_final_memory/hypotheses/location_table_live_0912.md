# location_table_live_0912

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 912
- updated_step: 1200
- depends_on: goal_crafting_table

## Statement

The claim that a crafting table was placed near (-3008,69,-5569) in this reset is false; the table remains an inventory item at step 1200.

## Evidence

- Step 912 records [INV] crafting_table -1 from pos (-3007.13,69.00,-5567.70), pitch 60, yaw -177, and the attached frame visibly shows the placed crafting table directly ahead.
- Step 912 consumed the crafting-table item during placement; step 919 records GUI open=True and use_item crafting_table +1 while aimed at the visible table.
- Current events contain no use_item entry and step_1200.png shows the table in hotbar slot 1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
