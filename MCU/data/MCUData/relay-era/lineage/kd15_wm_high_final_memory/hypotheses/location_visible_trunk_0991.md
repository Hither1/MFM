# location_visible_trunk_0991

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 991
- updated_step: 1200
- depends_on: resource_reset_three_logs

## Statement

The claim that a trunk is centered under the crosshair at step 1200 is false; the crosshair points across water to a dirt hillside while the actual trunk remains at the far-right edge.

## Evidence

- The step-991 frame shows a vertical spruce-bark column from roughly x=555 to the right edge, visually distinct from the dirt ledges that fooled aim_at_tree during the two prior attempts.
- At step 1179 a full-height spruce-bark face occupies roughly x=375-640 and reaches ground level in the live frame. The player is now 3.2 blocks east and one block lower than the step-991 viewpoint after the prior approach and sweep; the required visual correction is only about 13 degrees right from yaw -171.
- step_1179.png showed the trunk at right; after yaw reached 202, step_1200.png shows the bark face directly under the crosshair.
- Direct inspection of step_1200.png contradicts the old inherited segment's pose/frame interpretation, and no log event followed the aim report.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
