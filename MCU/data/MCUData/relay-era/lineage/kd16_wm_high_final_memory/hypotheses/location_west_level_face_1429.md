# location_west_level_face_1429

- kind: location
- status: stale
- confidence: 0.95
- created_step: 1429
- updated_step: 1653
- depends_on: location_north_dirt_stair_1198, mechanism_surface_stair_no_descent_1402

## Statement

The west-facing yaw-90 surface cut is not a viable level tunnel in its current geometry: it broke two grass blocks and advanced 1.7 blocks, then stalled without exposing stone.

## Evidence

- The step-1402 frame facing north shows a continuous raised dirt wall on the player's left (west), while only the northward staircase geometry has been tested and retired.
- At step 1653 mine_forward reported 2 blocks broken, 1.7 blocks advanced, and an early stop after two cycles failed to move; events contain only grass_block and no stone.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
