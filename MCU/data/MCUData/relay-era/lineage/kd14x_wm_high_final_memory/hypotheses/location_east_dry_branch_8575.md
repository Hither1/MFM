# location_east_dry_branch_8575

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 8575
- updated_step: 8687
- depends_on: location_midcorridor_bounded_shaft_6683, goal_mine_iron_ore

## Statement

The eastbound y60 face at yaw -90 from the dry shaft floor near (-3004.7,-5557.2) is not a productive level branch: it broke four blocks but advanced only 0.4 blocks before the verified no-movement stop.

## Evidence

- The west face at this origin just failed, while the only earlier east attempt was thirteen blocks south inside the known flooded zone; this dry-origin east face is untested.
- Steps 8600-8678 verified stone, dirt, stone, and grass breaks, but the step-8687 state remained at x=-3004.3 and strip_mine reported only 0.4 blocks advanced before stopping early.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
