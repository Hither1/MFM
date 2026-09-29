# resource_iron_fuel_gate

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 5400
- updated_step: 11000
- depends_on: location_reachable_spruce_5400, goal_mine_log, goal_furnace, resource_current_lighting_kit, location_current_crafting_table, resource_rebuild_stone_pick_7259, resource_surface_wood_after_furnace, location_surface_furnace_6279, location_live_fuel_spruce_8970, resource_live_log_drop_9107, location_live_trunk_view_9800

## Statement

The iron fuel gate is resolved at step 11000: the final ore and two sticks are in the burning furnace, so no wood or coal recovery is needed.

## Evidence

- events/events.jsonl records craft_item spruce_planks +4 at step 6736 and craft_item stick +4 at step 6768; authoritative step-6775 STATE lists spruce_planks x2 and stick x4, while the active 2x2 grid is empty. The remaining spruce_log cursor label is therefore stale consumed-item metadata.
- At steps 6821-6828 INV iron_ore -2 and the active furnace input prove both ores were deposited. At steps 6831-6840 INV spruce_planks -2, the active furnace input/fuel cells, and the visible flame prove both planks were loaded and smelting began; frame 6840 still shows an empty output slot despite a false-positive GRID out label.
- Two planks were loaded at 6840 and two ingot craft events followed; frame 8000 has ore x1 but no fuel stack.
- Frame 8600 shows ore x1 and no fuel; the previous two planks were consumed producing the two owned ingots.
- Frame 9200 shows ingots x2, ore x1, sticks x4, cobble x35 and no fuel; events verify a log break at 9107 but no pickup.
- No spruce-log pickup, plank craft, coal, or charcoal event occurs after step 9200. Steps 9495/9507 broke leaves, and two later 75-tick chops broke nothing.
- Events contain no log pickup, plank craft, coal, or charcoal after step 9200; frame 10400 still shows ore x1 and ingots x2 while placing the crosshair directly on fresh bark.
- INV iron_ore -1 at 10963, INV stick -4/+2 at 10976/10991, active furnace GRID [in,fuel], and frame 11000 flame jointly prove the gate is satisfied.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
