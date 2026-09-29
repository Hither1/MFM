# state_live_furnace_output_8193

- kind: state
- status: active
- confidence: 0.99
- created_step: 8238
- updated_step: 8261
- depends_on: goal_mine_iron_ore, goal_furnace, state_live_furnace_cursor_7607

## Statement

At live step 8261 the furnace GUI is open with two iron ore in input, no fuel, and one ready iron ingot in output; the obsolete wooden pickaxe is now genuinely held by the GUI cursor and zero-based hotbar slot 2 is free, so placing the pickaxe into fuel permits the ingot to be force-dropped and recollected.

## Evidence

- The step-8193 furnace GUI frame visibly shows input x2, an empty fuel slot, and output x1; relevant GRID reports furnace [in,out]. Events record craft_item iron_ingot +1 at step 7843 but no pickup iron_ingot, and authoritative step-8238 inventory has zero free slots and no iron ingot.
- Step 8261 reports GUI open, furnace [out], wooden_pickaxe x1 off-inventory, [INV] wooden_pickaxe -1, and zero free inventory slots only because the pickaxe remains on the cursor; frame 8261 visibly shows two ore in input and the ingot output.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
