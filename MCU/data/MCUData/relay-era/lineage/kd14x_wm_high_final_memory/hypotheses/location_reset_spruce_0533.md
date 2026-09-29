# location_reset_spruce_0533

- kind: location
- status: active
- confidence: 0.90
- created_step: 533
- updated_step: 773

## Statement

At step 773 the spawn-side spruce trunk is visibly close on the left from (-3008.23,70.00,-5569.70); the crosshair remains high on leaves/sky at pitch -39 and yaw 67, so a coarse target near pitch +8 and yaw 40 should put lower bark into view before closed-loop tree aiming.

## Evidence

- Historical evidence records a successful spruce break while adjacent at (-3008.78,73,-5569.73). At step 533 the player is at (-3005.70,68,-5564.96), about 5.7 horizontal blocks away, while the trunk is visibly high-left in frame and chop_tree reports out of reach.
- go_to returned from the y68 downhill area to this waypoint by step 563; step_0600.png directly shows the nearby trunk.
- The attached step_0773 frame shows a broad vertical brown spruce trunk left of center, while the last chop generated mine_block spruce_leaves and no log event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
