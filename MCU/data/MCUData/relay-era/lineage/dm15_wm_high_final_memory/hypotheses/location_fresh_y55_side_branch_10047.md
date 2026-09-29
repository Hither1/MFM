# location_fresh_y55_side_branch_10047

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 10047
- updated_step: 11400
- depends_on: location_fresh_y55_east_branch_8884, resource_stone_pickaxe_secure, resource_rebuild_stone_pick_7259, goal_mine_iron_ore, state_live_surface_empty_11400

## Statement

Refuted as duplicate-trajectory contamination: the live step-11400 player is at the surface spruce near (-3000.70,66,-5567.90), not in a y55 branch at (-3019.70,-5603.70).

## Evidence

- The latest ore-watched yaw-90 strip advanced 8.0 blocks to this endpoint and mined 17 stone with no iron; visited topology shows the proposed perpendicular direction is unsampled.
- visited.csv steps 10047-10200 proves the two-block southward advance; events 10068-10185 are six stone breaks only.
- Current-track visited rows 10200-10800 and STATE at 10774 show the extension; events through 10796 contain no iron.
- Live STATE/logs and current-track visited rows through step 11400 fix the endpoint; events from the branch contain stone, gravel, and andesite but no iron.
- The final visited.csv trajectory block, current events, and attached frame all match the surface tree; the y55 coordinates come from an earlier duplicate block.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
