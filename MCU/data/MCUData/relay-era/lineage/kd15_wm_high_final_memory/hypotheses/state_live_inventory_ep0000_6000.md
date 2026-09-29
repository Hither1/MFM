# state_live_inventory_ep0000_6000

- kind: state
- status: stale
- confidence: 1.00
- created_step: 6000
- updated_step: 7800
- depends_on: resource_current_iron_drop_5062, goal_furnace, resource_current_wood_fuel_ep0000_6000

## Statement

The step-7200 inventory snapshot is historical and superseded by the completed smelting/output manipulations at step 7800.

## Evidence

- Counts reconcile the step-5400 frame with pickups through 5715, the step-5994 cobble placement, 75 stone-pick uses, 32 wooden-pick uses, and step_6000.png.
- Event accounting from step 6000 subtracts five cobble, four granite, four andesite, ten diorite, and eight recipe cobble; adds dirt x2 and furnace x1. Frame 6600 visually agrees with the nine hotbar stacks/empties.
- Inventory deltas through 7095 and the enlarged step-7200 hotbar/furnace crops reconcile these counts; furnace input/fuel are visibly x3/x2.
- Since step 7200 the first ingot was banked and picked up, dirt increased by one, furnace input/fuel were consumed, and the last two ingots completed.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
