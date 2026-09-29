# resource_dropped_logs

- kind: resource
- status: refuted
- confidence: 0.05
- created_step: 1158
- updated_step: 1200
- depends_on: goal_mine_log

## Statement

The forced inventory close at step 1158 dropped two recoverable spruce logs at (-3000.70,65.00,-5564.53).

## Evidence

- The step-1158 harness note explicitly reports spruce_logx2 left off-inventory and dropped on the floor at pos (-3000.70,65.00,-5564.53), although the cursor label had previously appeared stale.
- The cursor item label was stale throughout verified crafting. Both picked logs are fully accounted for by two plank craft events, and no post-1158 spruce_log pickup event exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
