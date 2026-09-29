# state_diamond_clearance_11400_ep0000

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 11400
- updated_step: 11462
- depends_on: location_diamond_vein_10362, resource_diamond_capacity_9600

## Statement

By live step 11462 the center west-wall ray had broken two stone blocks and one gravel block without exposing diamond; a later sweep moved the player east to (-2998.88,9,-5572.46) and recollected the deliberately dropped gravel x3, leaving inventory full.

## Evidence

- Final visited.csv row gives the pose and camera; events records mine_block stone at 11394; frame step_11400 shows the iron pick attacking the overhead/front stone.
- Final visited.csv rows give the pose; events verify stone at 11365, gravel at 11389, and flint pickup at 11399; milestone count remains 9/24.
- Current events verify stone breaks at 11365, 11403, and 11417, gravel at 11389, flint pickup at 11399, and gravel pickup +3 at 11462; current STATE and visited.csv give the final pose and 0 free slots.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
