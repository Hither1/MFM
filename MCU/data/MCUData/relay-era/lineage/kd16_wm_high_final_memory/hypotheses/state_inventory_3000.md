# state_inventory_3000

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 3000
- depends_on: goal_stone_pickaxe, goal_wooden_pickaxe

## Statement

Live step-3000 inventory is spruce planks x3, sticks x2, wooden pickaxe with 18 uses left, dirt x3, and cobblestone x25, with four empty hotbar slots.

## Evidence

- Step-3000 hotbar frame plus pickup/use events from 2442-2984 reconcile these exact stack counts; 15 stone-pick use events imply about 116/131 uses remain.
- Eight cobblestone were consumed by furnace crafting, seven dirt were later placed, and the furnace was placed in-world.
- Step 2906 records pickup of spruce_planks +3 and stick +2 beside the banked wooden pickaxe; no later inventory-changing event occurs, all placement uses through 2984 consume nothing, and step_3000.png shows those three hotbar stacks.
- Events from 3018-3592 and the step-3600 frame show the later inventory and position.
- The current-reset event stream has 29 wooden-pick uses; pickups and placements reconcile cobblestone x8 and sticks x2, and step_3000.png visibly matches those three stacks.
- events record craft_item stone_pickaxe at 3377 and step_3600.png shows the current three stacks.
- The hotbar zoom of step_3000.png shows stacks 3/2/pick/3/25; 35 cobblestone pickups minus 10 placements gives 25, 6 dirt pickups minus 3 placements gives 3, and 41 wooden-pick uses leave 18 of 59.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
