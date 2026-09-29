# state_current_cobble_socket_1784

- kind: state
- status: stale
- confidence: 1.00
- created_step: 1800
- updated_step: 2400
- depends_on: resource_live_cobblestone_1574, goal_mine_cobblestone

## Statement

The step-1784 cobblestone socket is resolved and empty: it broke at step 1859 and its drop was collected at step 1869.

## Evidence

- use_item cobblestone fired at step 1784, pose and aim remain unchanged through maps step 1800, and the latest frame shows a heavily cracked cobblestone face centered on the crosshair without a mine_block event.
- events records MILESTONE mine_cobblestone and mine_block cobblestone at 1859, then pickup cobblestone at 1869.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
