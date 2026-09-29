# location_west_level_cut_5203

- kind: location
- status: stale
- confidence: 1.00
- created_step: 5203
- updated_step: 6000
- depends_on: location_surface_return_4659, goal_mine_iron_ore

## Statement

This west-cut hypothesis belongs to a different reset trajectory and is not a live route in the final reset segment.

## Evidence

- The failed west stair still advanced one block through dirt, and the current frame shows a continuous dirt wall ahead; a level cut tests whether the obstruction is limited to staircase geometry.
- maps/visited.csv moves from x=-3002.59 at step 5205 to x=-3005.70 at step 5400; events record six dirt breaks and one stone break during the cut, and the step-5400 frame shows an enclosed corridor with stone at the lower face.
- The step-5595 mine_forward note reports 11 blocks broken and 4.2 blocks advanced in the latest segment; position moved west to x=-3007.70, events include two more stone breaks, and the current frame shows stone flooring beneath the dirt face.
- Level calls advanced 3.1 and 4.2 blocks and exposed stone/coal; west stair at step 5693 and yaw-0 stair at step 5954 each stopped with zero descent.
- At current step 5203 the final visited segment is at (-2988.30,44,-5568.70), not the claimed x=-3002..-3009 y63 corridor.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
