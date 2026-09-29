# location_midcorridor_north_branch_6445

- kind: location
- status: refuted
- confidence: 0.90
- created_step: 6445
- updated_step: 6574
- depends_on: goal_mine_iron_ore

## Statement

The north branch from the corridor midpoint near (-3005,63,-5558.3) is blocked geometry and should not be mined again.

## Evidence

- The east-west corridor is traversable and this branch origin is several blocks away from both refuted endpoint faces; its north wall has not yet been tested.
- At step 6574 mine_forward broke four dirt blocks but advanced only 0.4 blocks and stopped after two cycles without movement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
