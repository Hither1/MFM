# location_south_level_cut_5954

- kind: location
- status: refuted
- confidence: 0.90
- created_step: 5954
- updated_step: 6253
- depends_on: location_south_stair_5753, goal_mine_iron_ore

## Statement

The yaw-0 south level cut from (-3008.99,63,-5558.30) is blocked geometry: repeated clearing broke blocks but produced no forward advance, so this face should not be mined again.

## Evidence

- The failed south stair exposed coal at the crosshair, while the earlier west level cut proved that clearing a level corridor can penetrate the hill despite staircase stalls.
- Events verify coal_ore broken at 5975 and stone at 5993; maps/visited.csv remains fixed at the origin through step 6000.
- At step 6121 mine_forward broke stone, then the watcher stopped on speckles at image coordinate (209,284). A 4x zoom of the flag-time frame shows those pixels belong to a floating dirt item in shadow, not an ore block.
- At step 6253 mine_forward reported 2 blocks broken and 0.0 blocks advanced over 133 ticks, after earlier clearing also failed to establish movement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
