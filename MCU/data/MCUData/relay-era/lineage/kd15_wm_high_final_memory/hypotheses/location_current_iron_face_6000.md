# location_current_iron_face_6000

- kind: location
- status: active
- confidence: 0.99
- created_step: 6000
- updated_step: 6600
- depends_on: goal_stone_pickaxe

## Statement

The step-6247 pose (-2986.70,44,-5580.29) with pitch 48 and yaw 196 is the only current-run reproducible sightline to visible iron: the ore cluster is high-left in that frame, while neither inherited approximate center is an exact block target.

## Evidence

- maps/visited.csv step 6000 fixes the live pose; ore_registry records the persistent vein and a prior break from nearly the same approach. The dark frame does not visually separate ore texture, so the coordinate is the discriminating test.
- Step-6247 magnified crop of the upper forward wall visibly separates multiple brown/tan-speckled ore textures from the plain stone under the crosshair. Steps 6007-6167 aimed at the lower coordinate and broke six stone blocks with no iron event, falsifying that exact ray.
- A magnified step-6247 frame clearly shows tan-speckled iron in the upper-left wall. Events from the two later fixed rays contain only stone and diorite, so they do not invalidate the visual sighting but do invalidate the guessed centers.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
