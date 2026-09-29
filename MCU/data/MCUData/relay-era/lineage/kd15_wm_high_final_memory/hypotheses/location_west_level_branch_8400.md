# location_west_level_branch_8400

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 8400
- updated_step: 8575
- depends_on: location_midcorridor_bounded_shaft_6683, goal_mine_iron_ore

## Statement

The westbound y60 face at yaw 90 from the dry shaft floor near (-3004.7,-5557.2) is not a productive branch: two verified mining cycles broke four blocks but advanced only 0.4 blocks.

## Evidence

- Visited coordinates show only the southward y60 line at x=-3004.3; the water failures occurred around z=-5545, while the shaft floor near z=-5558.3 was previously stable and dry.
- Step 8575 strip_mine report: broke 4 blocks, advanced 0.4 blocks in 101 ticks, then stopped after two cycles without avatar movement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
