# location_reset_spruce_0533

- kind: location
- status: active
- confidence: 1.00
- created_step: 533
- updated_step: 600

## Statement

The step-773 spawn-spruce pose belongs to a different trajectory and is not a live waypoint in the reset currently at step 600.

## Evidence

- Historical evidence records a successful spruce break while adjacent at (-3008.78,73,-5569.73). At step 533 the player is at (-3005.70,68,-5564.96), about 5.7 horizontal blocks away, while the trunk is visibly high-left in frame and chop_tree reports out of reach.
- go_to returned from the y68 downhill area to this waypoint by step 563; step_0600.png directly shows the nearby trunk.
- The attached step_0773 frame shows a broad vertical brown spruce trunk left of center, while the last chop generated mine_block spruce_leaves and no log event.
- The latest-reset map ends at step 600 at (-3004.79,68,-5566.27); no live step 773 exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
