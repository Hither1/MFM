# location_current_diamond_descent_8124

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 8124
- updated_step: 8600
- depends_on: goal_iron_pickaxe, goal_mine_diamond_ore

## Statement

Refuted for the live trajectory: no western diamond-descent shaft at (-3000.70,-5565.36) currently exists.

## Evidence

- Live STATE at step 8124 gives (-2999.26,65.00,-5565.21), GUI closed; furnace placement consumed one furnace at step 8122 and the iron pickaxe is banked in hotbar slot 1.
- Frame step_8125 shows the furnace top directly under the crosshair while pitch=90, and the step-8125 dig_down consumed its aiming segment with no position change or mine_block event.
- The furnace placement/use at 8122/8125 produced no descent there, while final visited.csv rows show the adjacent shaft descending continuously to y52.
- Current frame/map place the player at (-2996.70,55,-5564.70), still returning for the uncrafted iron pick; no matching descent events exist by 8600.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
