# location_return_gap_6946

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 6946
- updated_step: 7800
- depends_on: location_y56_west_strip_4800, location_y56_furnace_4810

## Statement

The former low-corridor choke at x about -2992 is cleared and traversable; it no longer blocks the route between the iron wall and shaft-foot furnace.

## Evidence

- At step 6946, go_to had stopped at x=-2991.7 and mine_forward broke two blocks without advancing; the attached west-facing frame clearly shows an open lit corridor with a dark one-block floor depression directly ahead rather than a wall.
- At step 6954 use_item dirt verified bridge placement, yet go_to at step 6959 moved zero. The attached frame shows a straight lit corridor west with no full-height wall.
- Step 6954 verified dirt placement. go_to at 6959 moved zero, and travel through 7059 only oscillated y from 56.00 to 56.20 without horizontal displacement while the attached frame still showed an open corridor.
- Frames 6946, 7099, and 7123 show the same dark floor gap. After use_item dirt at 6954, a dirt top appears beneath the foreground/player, while go_to, jump travel, and plain forward all remain fixed at x=-2991.70.
- Frames 6946-7123 show the lit west corridor with a centered raised foot block; go_to, plain forward, and jump-forward all made zero progress. Dirt placement at 7131 changed inventory but still did not permit movement.
- use_item dirt fired at 6954 and 7131; all crossing attempts remained at x=-2991.70; mine_block dirt fired at 7176 and 7197 while maps/visited.csv remained fixed through 7200; the live frame still centers dirt.
- Events verify both dirt breaks at 7176/7197 and a stone break at 7233; STATE remains (-2991.70,56,-5566.70) through a 60-tick forward test ending 7294, while the magnified live frame visibly shows a centered full stone front face immediately ahead.
- After dirt/stone clearance, maps show movement to (-2992.82,55,-5566.40) at 7450; go_to then moved 8.43 blocks west by 7613 and reached the furnace pose by 7619.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
