# location_west_hill_stair_5094

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 5094
- updated_step: 5693
- depends_on: location_surface_return_4659, goal_mine_iron_ore, location_west_level_cut_5203

## Statement

Westward stair descent is not viable in the current corridor geometry: attempts from both x=-3001.3 and the deeper x=-3007.7 face stalled after about one block of advance and zero descent; use a perpendicular heading from the current mine face instead.

## Evidence

- Step 5094 daylight frame while facing south shows a rising dirt/grass hillside directly to the player's right (west); this heading has not been tested from the recovered surface position.
- At step 5203 stair_down west reported 3 blocks broken, 1.0 block advanced, 0.0 descended, followed by 96 ticks with no depth gain.
- Step 5203 west stair broke 3/advanced 1.0/descended 0.0; step 5693 repeated from the deeper face, broke 3 including two coal ore, advanced 1.0, descended 0.0, then reported 96 ticks with no depth gain.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
