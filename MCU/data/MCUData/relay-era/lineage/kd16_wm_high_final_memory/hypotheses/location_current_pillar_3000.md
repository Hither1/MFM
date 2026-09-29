# location_current_pillar_3000

- kind: location
- status: stale
- confidence: 1.00
- created_step: 3000
- updated_step: 3600
- depends_on: location_stone_face_1800, mechanism_dirt_pillar_return_2325, location_current_iron_approach_3600

## Statement

The step-3000 return pillar is historical; the live player is now at (-2995.30,67.00,-5571.70) on a new three-dirt escape pillar near the iron approach.

## Evidence

- maps/visited.csv step 3000 gives the in-flight pose; only dirt uses at 2972 and 2984 are event-verified, so two lasting levels—not the transient y66.25 jump height—have been added.
- maps records y69 by step 3050 and current step-3600 pose (-3003.50,67.00,-5565.24).
- The final current-reset visited row at step 3000 gives the pose; steps 2948-2976 gained no y and step_3000.png shows a dark overhead block.
- Visited rows rise from y61 at step 3000 to y68 by 3310; current pose is y67 and the frame looks down into the reopened entrance.
- The last row of the final step-0 segment in maps/visited.csv is step 3000 at this exact pose; use_item cobblestone fired at 2981 and 2993 and raised settled y61 to y63.
- Final-reset visited rows at step 3600 give the new pose, and dirt uses at 3576/3584/3596 establish the new pillar.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
