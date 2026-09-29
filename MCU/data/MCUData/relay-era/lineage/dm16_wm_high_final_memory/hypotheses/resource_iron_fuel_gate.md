# resource_iron_fuel_gate

- kind: resource
- status: confirmed
- confidence: 0.99
- created_step: 5400
- updated_step: 6000
- depends_on: location_reachable_spruce_5400, goal_mine_log, goal_furnace, resource_current_lighting_kit, location_current_crafting_table, resource_rebuild_stone_pick_7259, resource_surface_wood_after_furnace, location_surface_furnace_6279, location_live_fuel_spruce_8970, resource_live_log_drop_9107, location_live_trunk_view_9800, location_surface_furnace_3591, mechanism_sticks_as_furnace_fuel_5729

## Statement

The iron-fuel gate is resolved: the consumed wooden pickaxe plus two deposited sticks provide the 400 burn ticks needed for the last two ore, while two recipe sticks remain banked.

## Evidence

- No spruce-log pickup, plank craft, coal, or charcoal event occurs after step 9200. Steps 9495/9507 broke leaves, and two later 75-tick chops broke nothing.
- Events contain no log pickup, plank craft, coal, or charcoal after step 9200; frame 10400 still shows ore x1 and ingots x2 while placing the crosshair directly on fresh bark.
- INV iron_ore -1 at 10963, INV stick -4/+2 at 10976/10991, active furnace GRID [in,fuel], and frame 11000 flame jointly prove the gate is satisfied.
- Current-prefix events contain no retained fuel acquisition, frame 4800 shows sticks x4 and no fuel stack, and the prior resolved-at-11000 statement is future-trajectory contamination.
- Step-5006 STATE authoritatively lists spruce_planks x1, wooden_pickaxe x1, and sticks x4. The existing measured model gives 200 ticks per ore and confirms two sticks fuel one smelt; the wooden-tool/plank portions remain to be tested in the furnace.
- At step 5278 INV records spruce_planks -1; after the cursor landed on furnace fuel and clicked, the active furnace row at step 5283 is [in,fuel,out] while the frame visibly shows iron ore x3 in input and smelting progress. The lingering ore/plank cursor labels match the already-confirmed stale-label mechanism.
- craft_item iron_ingot fired at step 5491 and the ingot was recovered at 5568; current STATE has iron_ingot x1, wooden_pickaxe x1, and sticks x4, while the prior active furnace GRID retained input after the first output was taken.
- Wooden pick INV -1 at 5713, sticks INV -4/+2 at 5724/5737, second ingot craft at 5945, and frame 6000 shows the final ore still burning on stick fuel.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
