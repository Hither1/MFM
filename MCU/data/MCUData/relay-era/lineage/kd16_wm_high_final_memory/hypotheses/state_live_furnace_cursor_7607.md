# state_live_furnace_cursor_7607

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 7607
- updated_step: 7607
- depends_on: goal_mine_iron_ore, goal_furnace, resource_iron_ore_drop_6296, location_live_furnace_worksite_6473

## Statement

At live step 7607 the furnace GUI is open and empty, and all three mined iron ore are confirmed on the GUI cursor over zero-based hotbar slot 3; placing them in furnace input will free that player slot for the first ingot pickup.

## Evidence

- Authoritative step-7607 STATE reports GUI open=True and CURSOR iron_ore x3; the attached frame visibly shows the furnace screen, empty input/fuel/output, and inventory spruce_planks x7.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
