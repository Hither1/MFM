# mechanism_aim_tree_held_log_false_positive_1200

- kind: mechanism
- status: active
- confidence: 0.85
- created_step: 1200
- updated_step: 1200
- depends_on: location_live_right_spruce_1103, state_inventory_1200

## Statement

When a spruce log is held and world bark sits at the image edge, aim_at_tree can report centered bark even though the crosshair is not on a trunk.

## Evidence

- At step 1128 aim_at_tree reported 5,030 bark pixels and centered alignment, but step_1200.png at the unchanged pose/yaw shows the crosshair on the opposite hillside, world bark at far right, and a large held-log model in the lower right; no log event occurred.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
