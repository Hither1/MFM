# location_furnace_drop_3276

- kind: state
- status: stale
- confidence: 1.00
- created_step: 3365
- updated_step: 3600
- depends_on: goal_furnace

## Statement

The step-3276 furnace-drop episode is resolved: pickup furnace fired at 3366, and that item was later placed elsewhere at step 3582.

## Evidence

- use_item furnace fired at 3215, mine_block furnace fired at 3276, furnace disappeared from inventory after placement, and both later sweeps reported no pickup while STATE had zero free slots.
- logs.txt records [INV] furnace +1 at step 3367, and the authoritative step-3574 inventory lists furnace x1.
- events records mine_block furnace 3276, pickup furnace 3366, and later use_item furnace 3582.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
