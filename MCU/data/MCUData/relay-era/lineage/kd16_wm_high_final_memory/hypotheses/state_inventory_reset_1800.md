# state_inventory_reset_1800

- kind: state
- status: stale
- confidence: 1.00
- created_step: 1800
- updated_step: 1800
- depends_on: goal_mine_log, resource_reset_three_logs

## Statement

The ancestor-reset step-1800 snapshot claiming only one spruce log is not live state and must not guide current inventory accounting.

## Evidence

- events.jsonl has one spruce-log pickup at 914 and no later inventory/craft event through 1800; the step-1800 hotbar shows only the selected log.
- Current-reset events verify wooden_pickaxe at 1480 and four dirt pickups through 1788; step_1800.png shows dirt x4, sticks x2, and the wooden pick, contradicting the inherited one-log snapshot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
