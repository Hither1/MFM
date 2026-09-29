# state_inventory_6000

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 6000
- updated_step: 6000
- depends_on: mechanism_torch_recipe_5707, goal_furnace, goal_stone_pickaxe

## Statement

At live step 6000 the hotbar holds wooden pickaxe with 26 uses, cobblestone x37, dirt x8, sand x2, stone pickaxe with 82 uses, furnace, granite x13, then two empty slots; no wood, sticks, coal, torch, ore, or ingot is held.

## Evidence

- Counts are reconciled from the step-6000 frame and events through 6000. Coal broken at 5975 and stone at 5993 lack pickup events and are not included.
- Events through 6582 and the step-6600 hotbar show changed cobblestone, dirt, torch, tool durability, and no held furnace.
- Step-6000 frame gives stack counts; events total 29 wooden-pick and 92 stone-pick uses and reconcile all pickups/placements.
- Events from 6066-6587 and the step-6600 frame show changed tool durability and diorite/cobblestone counts.
- Counts are legible in the step-6000 frame and reconcile with events; 64 stone-pick use events leave 67 durability.
- Current ground-truth events stop at 4800 and contain no wood, coal, torch, or furnace event.
- The step-6000 frame gives stack counts; the current event stream has 33 wooden-pick and 49 stone-pick uses and no iron/wood/coal acquisition after the shown crafts.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
