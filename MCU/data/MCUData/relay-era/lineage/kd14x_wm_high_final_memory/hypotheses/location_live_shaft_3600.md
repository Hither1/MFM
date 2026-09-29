# location_live_shaft_3600

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 3600
- updated_step: 10800
- depends_on: goal_mine_cobblestone

## Statement

The current-reset shaft connects (-2999.5,67,-5576.7) to y9, then to the north tunnel and confirmed diamond pocket near (-2999.3..-2999.7,9,-5571.11); the live step-10800 pose is (-2999.30,9,-5571.11).

## Evidence

- At step 8477 left x3 moved x=-2999.18 to -2999.61 as predicted, but the following dig_down spent its startup budget with y fixed at 67 and no block event. The attached pitch-88 frame visibly places the open shaft immediately ahead of the crosshair, motivating a minimal forward-entry test rather than further side-wall attack.
- Authoritative poses: step 8477 (-2999.61,67,-5576.72), then forward x4 at yaw -176 reached (-2999.76,67,-5577.35). The attached step-8481 frame shows the shaft opening behind/south of the crosshair. Prior successful current-reset descent began near (-2999.49,-5576.70). Exact-400 plans truncated dig_down before any environment ticks, so n=340 leaves steering headroom.
- At steps 8485-8825, after correcting to (-2999.34,67,-5577.09), dig_down broke 17 diorite/stone/granite blocks and descended 10.5 blocks to (-2999.30,56.54,-5576.93); the next state settled at y56.23.
- Current-reset map rows show the 8485-8825 descent to y56.23 and iron-pick breaks at 8916-8972 carrying the player to y48; rows 8999-9000 settle at y47.77.
- Visited rows 8999-9199 preserve x=-2999.56,z=-5576.34 while y falls from 47.77 to 28.00; ordinary block-break events continue through step 9185. The harness then reports 4 damage at y28 and interrupts the plan.
- Final current-reset map rows show y47.77 at 9000, y28 at 9199, y9 at 9511, and (-2999.70,10.17,-5576.30) at 9600, with continuous ordinary block-break events during descent.
- Final matching visited rows verify the continuous descent to y9, north-tunnel advancement through step 10151, retreat along the tunnel, and step-10200 pose/pitch/yaw (-2999.70,9,-5571.11,35,90).
- The current trajectory's logs and map rows verify the shaft descent, tunnel, three diamond breaks, and final step-10800 pose; all similarly numbered y44/y64 rows belong to other trajectory segments.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
