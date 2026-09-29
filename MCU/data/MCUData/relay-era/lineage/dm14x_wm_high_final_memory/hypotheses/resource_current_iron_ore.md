# resource_current_iron_ore

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 7800
- updated_step: 6600
- depends_on: goal_mine_iron_ore, location_iron_candidate_8218, location_live_iron_floor_6282, resource_iron_fuel_gate, location_y56_furnace_4810, location_live_iron_pocket_4800, goal_furnace

## Statement

The third ore is consumed and converted: three iron ingots are owned, no iron ore is authoritatively inventoried, and the post-smelt ore cursor label is phantom.

## Evidence

- events lines 300/305 record two iron-ore pickups; no later ore consumption or pickup exists through 4800.
- Two ore were loaded at 4936; furnace GRID still showed [in] at 5152 after ingot #1 completed, current inventory has no ore, and the attached step-5211 furnace is visibly burning.
- Two ore were loaded at 4936; craft_item iron_ingot fired once at 5160, frame 5400 visibly shows the second output, and no ore stack remains.
- craft_item iron_ingot +1 fired at 5419 and the authoritative step-5644 inventory reports iron_ingot x2 with no ore; the furnace GRID contains only fuel.
- mine_block iron_ore fired at step 5774, pickup iron_ore fired at 5784, and the authoritative step-5880 inventory reports iron_ore x1 plus iron_ingot x2.
- mine/pickup iron_ore fired at 5774/5784; INV iron_ore -1 at 5892; the attached step-6000 frame visibly shows ore in furnace input, active flame/progress, empty output, and ingots x2 in slot 7.
- craft_item iron_ingot fired at step 6107 and authoritative step-6111 STATE reports iron_ingot x3; CURSOR still reports iron_ore x1 while the active furnace GRID contains only fuel.
- Furnace input emptied, craft_item iron_ingot fired at 6107, and INV iron_ingot +1 fired at 6111. The cursor label persisted but no INV or pickup restored iron ore through 6600.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
