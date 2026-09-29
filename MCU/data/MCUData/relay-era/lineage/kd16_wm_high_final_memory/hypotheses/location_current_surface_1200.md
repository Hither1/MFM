# location_current_surface_1200

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 1200
- updated_step: 1200
- depends_on: location_table_live_0912, location_north_dirt_stair_1198, resource_reset_three_logs, location_visible_trunk_0991

## Statement

The previously stored step-1200 pose (-3004.43,68,-5568.70) belongs to an older trajectory and is not the live reset's current location.

## Evidence

- maps/visited.csv step 1200 gives the exact pose; events contain no stone break and stair_down reported zero descent.
- maps/visited.csv and step-2400 state provide the newer exact pose after shaft excavation and pillar return.
- maps/visited.csv rows 1194-1200 fix the pose; step_1200.png shows the adjacent right-hand trunk, and events contain no use_item or craft event.
- The final maps/visited.csv row gives the pose; step_1200.png shows bark at the crosshair; no use_item event exists.
- The final current-reset map row gives (-3002.65,67,-5568.29), pitch 35, yaw 165 at step 1200.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
