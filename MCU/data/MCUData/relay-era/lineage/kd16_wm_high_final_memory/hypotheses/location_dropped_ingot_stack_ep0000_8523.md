# location_dropped_ingot_stack_ep0000_8523

- kind: location
- status: active
- confidence: 0.90
- created_step: 8523
- updated_step: 9419
- depends_on: goal_iron_ingot, state_live_furnace_output_8193

## Statement

The destroyed furnace has just released its three completed ingots at the former furnace tile near (-2985.5,43,-5577.5); the older wooden and stone pickaxe drops overlap the same approach, and three empty hotbar slots should hold all three stacks.

## Evidence

- events records craft_item iron_ingot +2 at step 8274 followed by a forced GUI close; the authoritative step-8523 inventory has no ingot and zero free slots, while the zoomed live frame visibly shows the silver ingot item sprite at the furnace face.
- Zoomed step_8559 frame shows the silver dropped-item sprite overlapping the furnace face. collect_drops at steps 8323 and 8559 changed no inventory, and the latter occurred after stone_pickaxe -1 freed hotbar slot 5.
- The output click at step 8272 occurred while the cursor still held wooden_pickaxe x1 and caused no ingot inventory delta; the forced close explicitly dropped that pickaxe. A stone pickaxe was then force-dropped at step 8535. No furnace break or pickup iron_ingot event exists through step 8799.
- The furnace output previously held all three crafted ingots and no pickup event occurred. Frame 9419 first shows the furnace gone after a continuous 380-tick hand break, with item entities still visible in the former block area.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
