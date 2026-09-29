# location_step1371_right_spruce

- kind: location
- status: stale
- confidence: 0.99
- created_step: 1371
- updated_step: 2400
- depends_on: resource_reset_three_logs

## Statement

The old centred spruce lead near (-3002.2,67,-5566.7) is stale after the player moved to (-2999.75,65,-5565.55); its unchanged ray had already timed out and should not guide the next chop.

## Evidence

- The attached step_1371 frame shows the trunk spanning approximately screen x=460..575 with its lower bark face at crosshair height; the player is among adjacent trunks on the hillside.
- The attached step_1628 frame shows the trunk spanning roughly screen x340-405 while the crosshair is at x320; prior chops at unchanged yaw -145 timed out without any block event, confirming the ray remained left of bark.
- The attached step-1800 frame and a 4x crop of pixels (280,140,100,100) show bark directly under the crosshair; map rows 1753-1800 show a stationary pose.
- The attached step_1876 frame visibly centres bark, while logs.txt records chop_tree ending at step 1828 with no mine event and an explicit out-of-reach/sky diagnosis.
- Map tail gives the step-2400 pose; the old ray produced a 75-tick no-break diagnosis and subsequent movement left the location.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
