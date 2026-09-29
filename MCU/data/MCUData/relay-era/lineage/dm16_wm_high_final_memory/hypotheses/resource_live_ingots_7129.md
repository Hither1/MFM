# resource_live_ingots_7129

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 7129
- updated_step: 6000
- depends_on: goal_iron_ingot, resource_iron_fuel_gate, location_surface_furnace_6279

## Statement

Refuted for the authoritative step-6000 prefix: the claimed step-11203 three-ingot state is future-trajectory contamination; only two ingots are currently secured.

## Evidence

- Two ore and two planks were loaded at steps 6828-6840; the first ingot completed at 7048, while the attached step-7129 frame still shows the furnace burning and inventory contains the first ingot.
- craft_item iron_ingot fired at 7048 and 7268, INV added ingots at 7129 and 7272, and frame 8000 shows ingot x2.
- Craft events fired at 7048/7268, and frame 8600 still shows ingot x2 with no later consumption.
- Frame 11000 visibly shows iron_ingot x2 in zero-based hotbar slot 3, and no later event or INV delta consumed them.
- The furnace output was taken at step 11197; craft_item iron_ingot fired at step 11199, INV iron_ingot +1 fired at step 11203, and authoritative STATE now reports iron_ingot x3 plus stick x2.
- Current events end at step 5945 and frame 6000 shows two ingots plus one ore still smelting; steps 7129/11203 have not occurred in this prefix.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
