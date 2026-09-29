# state_current_furnace_smelt_ep0000_7070

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 7070
- updated_step: 7800
- depends_on: location_current_surface_furnace_ep0000_7002, resource_current_wood_fuel_ep0000_6000, goal_mine_iron_ore, goal_furnace, goal_iron_ingot

## Statement

The three-ore furnace batch is complete: one ingot was extracted and milestone-picked up, while the remaining two ingots are visibly stacked in the furnace output at step 7800.

## Evidence

- At step 7070 the furnace GUI is open and empty; authoritative inventory reports iron_ore x3 in zero-based slot 7 and spruce_planks x2 in slot 5, with no cursor-held item.
- Logs 7076-7095 record ore/plank removal and furnace in/fuel occupancy; frame step_7200 visibly shows x3 input, x2 fuel, flames, and empty output.
- The first ingot craft fired at step 7303 and pickup at 7354. No furnace input or fuel was removed, and 259 burn ticks had elapsed by step 7354.
- The first ingot craft fired at step 7303, 208 ticks after loading. Continuous furnace operation predicts subsequent completions at roughly 7503 and 7703; the live step is 7554 and no furnace contents were disturbed.
- Loaded at 7095; first craft fired at 7303 and pickup at 7354. Step-7800 relevant GRID is furnace [out], input/fuel are empty, and the magnified frame shows output count 2.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
