# resource_current_iron_ore

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 7800
- updated_step: 11000
- depends_on: goal_mine_iron_ore, location_iron_candidate_8218, location_live_iron_floor_6282, resource_iron_fuel_gate, location_y56_furnace_4810, location_live_iron_pocket_4800, goal_furnace, location_visible_iron_7717

## Statement

The final owned iron ore was deposited into the surface furnace at step 10970; no iron ore remains in player inventory and that ore is currently smelting.

## Evidence

- mine/pickup iron_ore fired at 5774/5784; INV iron_ore -1 at 5892; the attached step-6000 frame visibly shows ore in furnace input, active flame/progress, empty output, and ingots x2 in slot 7.
- craft_item iron_ingot fired at step 6107 and authoritative step-6111 STATE reports iron_ingot x3; CURSOR still reports iron_ore x1 while the active furnace GRID contains only fuel.
- Furnace input emptied, craft_item iron_ingot fired at 6107, and INV iron_ingot +1 fired at 6111. The cursor label persisted but no INV or pickup restored iron ore through 6600.
- pickup iron_ore fired at 5176 and 5231; frame 5400 visibly shows iron ore x2 and current events contain no ore consumption.
- The step-6821 click removed iron_ore x2 from inventory, and the active furnace input remained occupied through step 6840 with two ore visibly present in the enlarged furnace frame.
- events records mine_block iron_ore at 7893 and pickup at 7903; frame 8000 visibly shows iron ore x1 in hotbar slot 6.
- Pickup iron_ore fired at 7903, no later ore consumption exists, and frame 8600 shows iron ore x1.
- INV iron_ore -1 at 10963 followed by active furnace input and frame 11000 ore/flame; the lingering cursor label is contradicted by inventory and GRID.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
