# mechanism_reclear_stair_headroom_9708

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 9708
- updated_step: 10800
- depends_on: mechanism_clear_south_step_ceiling_9544, location_south_diamond_stair_9349, goal_iron_pickaxe

## Statement

Repeated stair-headroom clearing is retired as conclusively slower than the completed direct shaft.

## Evidence

- The same overhead-clear and jump sequence moved 2.85 blocks at y60; the latest stair attempt gained one level before stopping after 96 ticks without further depth.
- Two cycles at steps 9708 and 9870 each required a 45-tick ceiling clear plus movement and a 97-tick stair call, yet each descended only about one block before another 96-tick no-depth stall.
- Two cleared stair cycles each cost about 160 ticks per level, while direct dig_down achieved 19 levels in 265 ticks.
- Two cycles cost about 160 ticks/level; direct digging reached y11 and the staircase has no remaining utility.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
