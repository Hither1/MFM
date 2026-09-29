# location_fresh_hillside_yaw122_11621

- kind: location
- status: stale
- confidence: 1.00
- created_step: 11621
- updated_step: 600
- depends_on: location_current_surface_11400

## Statement

The old yaw-122 hillside candidate is historical and should not guide the reset run.

## Evidence

- The step-11621 frame shows the crafting table ahead at yaw 32 and a dirt hillside continuing to the right; this direction has not appeared in the exhausted-route summary.
- Reset returned the player to spawn and no live route reaches that old pose.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
