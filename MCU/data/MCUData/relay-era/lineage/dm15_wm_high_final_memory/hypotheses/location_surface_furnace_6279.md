# location_surface_furnace_6279

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 6600
- updated_step: 6809
- depends_on: goal_furnace

## Statement

The placed spawn-grove furnace occupies block center (-3007.5,71.5,-5566.5); aiming at that exact center from (-3006.87,69.00,-5566.30) and using the selected stone pickaxe opened its empty furnace GUI at step 6809.

## Evidence

- INV furnace -1 at 6275 and events line 366 use_item furnace at 6279 prove placement; frame 6600 visibly centres the furnace from current pose (-3007.52,70,-5568.05).
- At step 6275 raw use from (-3006.70,70.18,-5566.30), pitch 34/yaw 59 removed the furnace; use_item fired at 6279. The ray crosses the north face at z=-5566 and places the furnace in the adjacent block centered (-3007.5,71.5,-5566.5); step-6600 frame independently shows that block directly south of the recorded pose.
- At step 6804 look_at targeted (-3007.5,71.5,-5566.5), and use_until_gui opened the furnace screen by step 6809; GUI open=True, cursor empty, and the active furnace grid had no occupied cells.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
