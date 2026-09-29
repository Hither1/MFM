# location_fresh_y56_east_branch_9587

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 9587
- updated_step: 5400
- depends_on: goal_iron_ingot, location_fresh_y56_south_furnace_branch_9216, resource_stone_pickaxe_secure

## Statement

Refuted as future-trajectory contamination; no step-9587 east branch exists in the current prefix.

## Evidence

- Visited topology shows the south branch endpoint is new and the perpendicular east face has not yet been mined.
- Events record wooden-pick stone breaks at 9707, 9738, and 9778; visited.csv ends at (-3004.30,56,-5560.58), and no iron event exists.
- Events record wooden-pick stone breaks at 9707, 9738, 9778, and 9809; step 9846 STATE and frame show the live east-facing tunnel face.
- Step 10135 strip_mine broke ten stone blocks and advanced 5.1 blocks from the prior endpoint, with no iron alert or iron event; authoritative STATE fixes the new endpoint and the frame shows intact stone ahead.
- visited.csv fixes the endpoint; events 10239-10379 add five wooden-pick stone breaks and no iron to the prior fourteen empty exposures.
- Attached step_10469.png shows multiple tan ore speckles embedded in the centered dark stone block directly ahead at yaw -90; live pose is (-2994.3,56,-5560.7).
- Steps 10497-10569 record five mine_block stone events and no iron event; step 10612 collected only cobblestone. The player subsequently traversed west from the opened face to (-3003.2,56,-5560.7).
- Current authoritative horizon is step 5400.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
