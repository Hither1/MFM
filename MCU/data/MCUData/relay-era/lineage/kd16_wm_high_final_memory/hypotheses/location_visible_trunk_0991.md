# location_visible_trunk_0991

- kind: location
- status: active
- confidence: 0.90
- created_step: 991
- updated_step: 757
- depends_on: resource_reset_three_logs

## Statement

At live step 757 an intact full-height spruce trunk fills the right side of the frame from the current pose near (-3003.8,68,-5568.5); turning from yaw 198 toward roughly 225 should center its lower bark face for an approach and reachability test.

## Evidence

- The step-991 frame shows a vertical spruce-bark column from roughly x=555 to the right edge, visually distinct from the dirt ledges that fooled aim_at_tree during the two prior attempts.
- At step 1179 a full-height spruce-bark face occupies roughly x=375-640 and reaches ground level in the live frame. The player is now 3.2 blocks east and one block lower than the step-991 viewpoint after the prior approach and sweep; the required visual correction is only about 13 degrees right from yaw -171.
- step_1179.png showed the trunk at right; after yaw reached 202, step_1200.png shows the bark face directly under the crosshair.
- The attached step-757 frame clearly shows a vertical spruce-bark column on the right extending to ground level; current ground-truth pose is (-3003.8,68,-5568.5), pitch 15, yaw 198 modulo 360.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
