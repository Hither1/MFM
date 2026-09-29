# location_fresh_y55_east_branch_8884

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 8884
- updated_step: 5400
- depends_on: location_fresh_y55_north_strip_8156, goal_mine_iron_ore, resource_stone_pickaxe_secure, resource_rebuild_stone_pick_7259

## Statement

Refuted as future-trajectory contamination; the current y55 branch is the documented L-route near z=-5559.7/-5564.7.

## Evidence

- The current north corridor is traversable, the east branch from its endpoint has not been visited, and the selected stone pickaxe has 101/131 uses left.
- Latest maps row at step 9000 is (-2997.70,55,-5578.70); events 8905,8925,8954,8974 verify four non-iron breaks.
- The step-9247 state gives the endpoint and the step 9001-9242 events verify 15 non-iron block breaks with 6.0 blocks of advance.
- maps/visited.csv through step 9600 ends at (-3010.70,55,-5578.70); the post-9247 extension broke 14 stone and advanced 8 blocks with no iron event.
- Current step is 5400; cited step-8884 evidence is outside the prefix.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
