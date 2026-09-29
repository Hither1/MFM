# resource_worksite_spruce_drop_8366

- kind: resource
- status: confirmed
- confidence: 0.90
- created_step: 8400
- updated_step: 8724
- depends_on: location_worksite_overhead_spruce_8062

## Statement

The loose spruce-log drop from the step-8366 overhead break was recovered at step 8724 and is now banked; it can supply the planks needed for sticks.

## Evidence

- The block broke at 8366 without pickup; sand x8 left inventory at 8375 and was force-dropped at 8378; no subsequent pickup event occurred through step 8400.
- The spruce block broke at 8366 with no log pickup through 8490. Sand was repeatedly repicked, explaining the failed sweeps; the furnace input is now empty and can store it losslessly.
- At step 8518 the sand stack was placed into the furnace input and [GRID] reported furnace [in]. The guarded normal close was refused only because furnace contents count as off-inventory; the harness explicitly states force-close is lossless for furnace-row contents.
- No log pickup occurred after the break at 8366, and collect_drops swept 120 ticks through step 8644 without inventory gain.
- At step 8724 collect_drops moved about 1.05 blocks from the worksite pose, inventory gained spruce_log x1, and events recorded pickup spruce_log +1. No new log block was broken after step 8366, so this is the outstanding drop.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
