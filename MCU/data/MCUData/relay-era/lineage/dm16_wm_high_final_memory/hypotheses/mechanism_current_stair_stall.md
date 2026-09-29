# mechanism_current_stair_stall

- kind: mechanism
- status: refuted
- confidence: 1.00
- created_step: 3000
- updated_step: 3600
- depends_on: location_shallow_stone_shaft, resource_rebuild_stone_pick_7259, mechanism_wrong_held_item_3530

## Statement

Refuted as a live-route diagnosis: current zero-result stair/mining calls were caused by holding a torch, and inherited post-3600 surface-stair evidence cannot describe this trajectory.

## Evidence

- The step-2999 note reports three blocks broken, 1.0 advanced, 0.0 descended, and 96 final ticks without depth.
- The latest west-facing attempt ended at step 6447 after breaking three dirt blocks but advancing only 0.4 and descending 0.0; earlier yaw-0 and east-facing attempts likewise gained no depth.
- Step 7588 stair_down diagnostic reports 0 descent; step 7707 mine_forward also advanced 0, while visited.csv verifies direct descent to y60 by 7796.
- Current map remains at the y55 shaft; the node's prior evidence cites steps beyond the live horizon.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
