# location_live_furnace_worksite_6473

- kind: location
- status: active
- confidence: 0.90
- created_step: 6600
- updated_step: 7446
- depends_on: goal_furnace, location_live_iron_approach_6459

## Statement

The live furnace occupies the floor block centered near (-2985.5,43.5,-5577.5), directly south behind the crafting table centered near (-2985.5,43.5,-5579.5); breaking the nearer table from the current north-side pose should expose the furnace face.

## Evidence

- From pose (-2985.30,44,-5578.70), yaw south, place_block removed furnace at 6470 and use_item furnace fired at 6473; exact target coordinates were not logged.
- Furnace placement fired at step 6473 from z=-5578.70 facing south. Table placement fired at step 6634 from z=-5581.28 facing south. The step-7062 go_to stopped at z=-5580.30, exactly against the inferred table block, and the later furnace interaction failed while facing back north.
- Furnace placement at step 6473 occurred from (-2985.30,44,-5578.70) while looking down and south; table placement at step 6634 occurred from z=-5581.28 with the same floor-placement geometry. Frame 7403 visually shows the crafting-table face centered and the furnace face immediately behind/down-right; the prior y=44.5 target hit the table's upper face, so y=43.5 is the block-center correction.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
