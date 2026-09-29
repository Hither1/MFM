# state_death_diamond_run_10624

- kind: state
- status: stale
- confidence: 1.00
- created_step: 10624
- updated_step: 5400
- depends_on: hazard_live_lava_pocket_10604

## Statement

This death-at-step-10624 record belongs to a prior trajectory and is stale; it is not a live state constraint at step 5400.

## Evidence

- Step-10624 STATE is the spawn position with empty inventory; the death note records the death/drop coordinates and the inventory delta removes every carried stack.
- The current prefix ends at 5400, has no death event, and frame/map show a healthy equipped player underground.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
