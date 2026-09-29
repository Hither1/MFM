# location_current_iron_approach_3600

- kind: location
- status: stale
- confidence: 1.00
- created_step: 3600
- updated_step: 4200
- depends_on: location_seed_north_iron_vein

## Statement

The step-3600 blocked surface approach is historical; current pose is back at the worksite, and the blockage argues for a fresh descent plus underground tunnel rather than repeating direct surface go_to.

## Evidence

- maps/visited.csv gives the exact pose; go_to at step 3567 reported blockage 10.9 blocks short after moving 8.9 blocks, and the final frame shows surrounding spruce terrain.
- Final-reset map row 4200 is (-3004.17,68,-5568.60); the earlier go_to diagnosis remains evidence against that surface line only.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
