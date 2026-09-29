# state_live_pocket_11400

- kind: state
- status: stale
- confidence: 1.00
- created_step: 11400
- updated_step: 4800
- depends_on: location_diamond_depth_shaft_10138

## Statement

The step-11400 pocket state belongs to another trajectory and is not live in the current reset ending at step 4800.

## Evidence

- maps/visited.csv fixes the pose through step 11400; events record mine_block dirt at 11400 and no pickups after the recovery deaths; the frame shows the dirt/grass pocket.
- Current ground-truth events and final visited segment end at step 4800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
