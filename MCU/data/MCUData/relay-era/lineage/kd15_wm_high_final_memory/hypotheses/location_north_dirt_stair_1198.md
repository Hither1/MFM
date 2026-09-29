# location_north_dirt_stair_1198

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 1198
- updated_step: 1200
- depends_on: goal_mine_cobblestone

## Statement

The alleged step-1198 north dirt stair attempt is not part of the current run; the live pose remained beside spruce bark and no stair_down action or descent occurred.

## Evidence

- The step-1198 frame visibly shows the raised grass block ahead-right while the table fills the left side; yaw is -177, so this face is north of the player.
- The newest frame shows the crosshair on the grass/dirt face after a 0.24-block east shift; table obstruction is now confined to the left edge.
- At step 1402 stair_down reported 5 blocks broken, 1.3 blocks advanced, 0.0 descended, and STOPPED EARLY after two cycles broke blocks without movement; this follows the step-1198 zero-break stall.
- logs.txt ends with the step-1180 turn toward the trunk, maps rows 1180-1200 remain y68, and the latest frame shows bark rather than a dirt stair face.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
