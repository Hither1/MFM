# mechanism_shaft_floor_fixed_aim_8898

- kind: mechanism
- status: confirmed
- confidence: 0.95
- created_step: 8898
- updated_step: 9000
- depends_on: location_live_shaft_3600, goal_mine_diamond_ore

## Statement

When dig_down is governor-blocked on a shaft lip, fixed downward mine_ahead can change the floor geometry and let gravity continue the descent; at this shaft it broke five blocks and lowered the player 7.23 levels in 80 ticks.

## Evidence

- Steps 8896-8898 show repeated dig_down truncation/no-op governor notices at nearly unchanged position, while the step-8898 center crop visibly shows a granite block directly under the pitch-88 crosshair.
- Events verify five iron-pick block breaks at 8916-8972, while maps move from y55.23 to y48.00 after mine_ahead(n=80).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
