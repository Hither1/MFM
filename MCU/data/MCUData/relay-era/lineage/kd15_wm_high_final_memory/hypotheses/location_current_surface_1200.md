# location_current_surface_1200

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 1200
- updated_step: 1200
- depends_on: location_table_live_0912, location_north_dirt_stair_1198, resource_reset_three_logs, location_visible_trunk_0991, location_live_right_spruce_1103

## Statement

At step 1200 the live pose is (-3001.72,66.00,-5563.68), pitch 5.1, yaw 320 (-40), GUI closed beside a pond with a spruce trunk at frame right.

## Evidence

- maps/visited.csv step 1200 gives the exact pose; events contain no stone break and stair_down reported zero descent.
- maps/visited.csv and step-2400 state provide the newer exact pose after shaft excavation and pillar return.
- maps/visited.csv rows 1194-1200 fix the pose; step_1200.png shows the adjacent right-hand trunk, and events contain no use_item or craft event.
- The final maps/visited.csv row gives the pose; step_1200.png shows bark at the crosshair; no use_item event exists.
- The final reset segment of maps/visited.csv ends with this exact pose, and the attached frame supplies the pond/trunk geometry.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
