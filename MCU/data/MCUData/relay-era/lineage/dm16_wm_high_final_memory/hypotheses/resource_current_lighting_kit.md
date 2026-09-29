# resource_current_lighting_kit

- kind: resource
- status: active
- confidence: 1.00
- created_step: 4800
- updated_step: 10800
- depends_on: resource_early_logs, goal_furnace, goal_stone_pickaxe, resource_surface_wood_after_furnace, resource_live_early_logs, resource_wooden_pickaxe_secure, resource_stone_pickaxe_secure, goal_mine_log, location_live_fuel_spruce_8970, location_deep_coal_shaft_8840

## Statement

No coal, sticks, or torches remain after coal x3 was force-dropped at 10652; lighting is unavailable, so only ore watching and the coordinate-directed endpoint test fit the budget.

## Evidence

- No coal pickup or torch craft/use exists in the current event prefix. Frame 4200 shows wooden pick, sticks x4, stone pick, dirt x3, and cobble x12 only; the two remaining planks were dropped at forced close 3654.
- No current-prefix coal pickup or torch craft/use exists, and frame 4800 shows sticks, two picks, dirt-like icon, and cobblestone but no fuel or light.
- Current-prefix events contain no coal pickup or torch/charcoal craft, and frame 6000 shows only ingots, sticks, dirt, stone pick, and cobblestone outside the furnace.
- Live step 6495 STATE gives pos=(-3000.72,66,-5565.21), only 0.25 blocks from the registered deep-coal column horizontally; inventory has a disposable dirt x3 stack, and the registered terrace spruce is about five blocks south.
- Events through 6600 contain no coal pickup or torch craft; step 6580 broke grass, while frame 6600 shows a trunk immediately left and several empty inventory slots.
- Events through 7200 contain no current coal pickup or torch craft/use; frame 7200 shows only tools, dirt, diorite, and cobblestone, while the player is already at y40.
- events records coal_ore break 7494 and coal pickup 7504, with no stick/torch craft or use through 7800; frame 7800 shows coal x1 and no torches.
- INV coal -3 and the forced-close note prove the last coal stack was dropped at 10652; no later coal pickup, stick pickup, torch craft, or torch use exists through 10800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
