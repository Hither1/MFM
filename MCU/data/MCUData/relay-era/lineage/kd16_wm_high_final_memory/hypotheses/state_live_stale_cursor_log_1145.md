# state_live_stale_cursor_log_1145

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 1145
- updated_step: 1200
- depends_on: resource_reset_three_logs, goal_crafting_table, state_stale_cursor_log_0882

## Statement

The step-1145 spruce_log x3 off-inventory label was stale: three picked logs are fully accounted for by three verified plank crafts, and no real log stack was dropped by the forced close.

## Evidence

- events/events.jsonl records three spruce-log pickups and spruce_planks +4 at steps 1009, 1068, and 1082; step 1116 verifies sticks +4; current inventory has no logs and the survival 2x2 row is empty despite CURSOR naming spruce_log x3.
- Events record three log pickups and three plank crafts; subsequent inventory holds six planks and four sticks with no log pickup after the forced close, and the step-1200 frame accounts for those materials.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
