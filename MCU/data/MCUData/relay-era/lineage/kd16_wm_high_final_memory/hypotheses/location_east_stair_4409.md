# location_east_stair_4409

- kind: location
- status: refuted
- confidence: 0.90
- created_step: 4409
- updated_step: 4523
- depends_on: state_stone_below_pit_2443, goal_mine_iron_ore

## Statement

The eastward staircase from the y62 north-tunnel endpoint is not viable in its current geometry: it broke three surface dirt/grass blocks but advanced only 0.4 blocks and descended 0.0 before stalling.

## Evidence

- The north-facing stair_down broke three blocks but stopped after gaining no further depth; the perpendicular east heading has not yet been tested from (-3001.7,62,-5564.0).
- At step 4523 stair_down(depth=8) reported three blocks broken, 0.4 advanced, 0.0 descended, then 96 ticks without depth gain.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
