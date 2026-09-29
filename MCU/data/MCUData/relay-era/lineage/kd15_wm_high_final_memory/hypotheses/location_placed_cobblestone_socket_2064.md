# location_placed_cobblestone_socket_2064

- kind: location
- status: stale
- confidence: 1.00
- created_step: 2265
- updated_step: 3000
- depends_on: goal_mine_cobblestone, mechanism_dirt_disposal_shaft_1813

## Statement

The this-run north-wall cobblestone socket was mined at step 2303 and is no longer an active target or landmark.

## Evidence

- At y58 and yaw -180, mine_ahead broke the eye-level stone socket at step 2027; dirt was placed there at step 2037 and mined at step 2061; use_item cobblestone then fired at step 2064. No later mine_block cobblestone event exists, and the failed attack occurred after the avatar hopped one block higher.
- events/events.jsonl records mine_block cobblestone and the mine_cobblestone milestone at step 2303.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
