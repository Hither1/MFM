# location_west_level_cut_5203

- kind: location
- status: confirmed
- confidence: 0.95
- created_step: 5203
- updated_step: 6000
- depends_on: location_surface_return_4659, goal_mine_iron_ore

## Statement

The level westward cut from (-3002.6,63,-5558.3) to about (-3009,63,-5558.3) is a confirmed hill entry and ore-search corridor, but its tested west and yaw-0 staircase faces are not viable descent starts.

## Evidence

- The failed west stair still advanced one block through dirt, and the current frame shows a continuous dirt wall ahead; a level cut tests whether the obstruction is limited to staircase geometry.
- maps/visited.csv moves from x=-3002.59 at step 5205 to x=-3005.70 at step 5400; events record six dirt breaks and one stone break during the cut, and the step-5400 frame shows an enclosed corridor with stone at the lower face.
- The step-5595 mine_forward note reports 11 blocks broken and 4.2 blocks advanced in the latest segment; position moved west to x=-3007.70, events include two more stone breaks, and the current frame shows stone flooring beneath the dirt face.
- Level calls advanced 3.1 and 4.2 blocks and exposed stone/coal; west stair at step 5693 and yaw-0 stair at step 5954 each stopped with zero descent.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
