# state_stone_below_pit_2443

- kind: state
- status: stale
- confidence: 1.00
- created_step: 2443
- updated_step: 3600
- depends_on: state_surface_stair_2400, goal_mine_cobblestone

## Statement

The claimed productive tunnel near (-3001.7,61,-5563.3) belongs to another reset trajectory and is not current live geometry; current reset is at the shaft lip near (-2999.06,67,-5575.70).

## Evidence

- The yaw-168 macros through step 2443 broke only dirt/grass and stalled or climbed, while the current ground level is y64; probing four blocks downward changes the geometry and should reach the stone layer.
- events/events.jsonl records mine_block stone at step 2516 and the step-2523 state remains at the break site with no cobblestone in inventory. The ore-watch flag was visually checked and is dirt, not iron.
- events/events.jsonl records mine_block stone at step 2516; step 2543 inventory lists exactly spruce_planks, sticks, and wooden_pickaxe with 0 slots free and no cobblestone pickup event.
- events verifies mine_block stone at 2516; maps verifies y62 occupancy; step_2890.png shows exposed stone and a cobblestone item entity.
- maps/visited.csv fixes the current endpoint at (-3001.70,61,-5564.70); events record stone breaks at 3429, 3460, 3500, 3531, and 3570 with corresponding cobblestone pickups.
- The last current-reset block of maps/visited.csv has bounds z >= -5576.70 but its step-3600 row is (-2999.06,67,-5575.70); current events have no five-stone sequence at steps 3429-3570.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
