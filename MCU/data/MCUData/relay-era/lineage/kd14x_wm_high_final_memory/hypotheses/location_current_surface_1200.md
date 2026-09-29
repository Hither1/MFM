# location_current_surface_1200

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 1200
- updated_step: 1200
- depends_on: location_table_live_0912, location_north_dirt_stair_1198, resource_reset_three_logs, location_visible_trunk_0991

## Statement

At step 1200 the player is at (-3004.43,68.00,-5568.70), pitch 14.0, yaw 202.0 (-158), with an adjacent spruce trunk under the crosshair and no table placed.

## Evidence

- maps/visited.csv step 1200 gives the exact pose; events contain no stone break and stair_down reported zero descent.
- maps/visited.csv and step-2400 state provide the newer exact pose after shaft excavation and pillar return.
- maps/visited.csv rows 1194-1200 fix the pose; step_1200.png shows the adjacent right-hand trunk, and events contain no use_item or craft event.
- The final maps/visited.csv row gives the pose; step_1200.png shows bark at the crosshair; no use_item event exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
