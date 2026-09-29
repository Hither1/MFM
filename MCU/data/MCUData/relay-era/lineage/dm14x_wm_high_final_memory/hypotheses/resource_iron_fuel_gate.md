# resource_iron_fuel_gate

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 5400
- updated_step: 6600
- depends_on: location_reachable_spruce_5400, goal_mine_log, goal_furnace, resource_current_lighting_kit, location_current_crafting_table, resource_rebuild_stone_pick_7259

## Statement

The iron fuel gate is closed and satisfied: all three required ingots have been produced, so no further ore or fuel is needed for the iron pickaxe.

## Evidence

- Live inventory has 69 cobblestone and three sticks; two sticks plus three cobblestone can craft the replacement pick, while the known table above the traversable shaft is a recoverable wooden fuel item. This turn tests ascent and table recovery.
- No coal/log/plank pickup follows the prior smelts; current inventory evidence is cobblestone and sticks only. Table access is confirmed, but ore acquisition plus descent/smelt exceeds the remaining budget.
- Two live coal pickups are verified; one coal remains after the planned one-coal torch recipe and can smelt three ore.
- One coal was returned during the verified torch recipe; frame 3530/3600 shows coal x1 and no later coal use event.
- Frame 4800 shows coal x2; fresh mine/pickup coal events fired at 4770/4780 and no coal use event exists.
- Frame 5400 shows active flame with empty fuel/input, coal x1 and plank x1 in hotbar; one coal already smelted both owned ore.
- Step-6000 furnace frame shows input ore, plank fuel, flame and partial progress; output remains empty because the measured ~200-tick smelt is incomplete.
- The third craft_item iron_ingot event fired at 6107 and three ingots were inventoried by 6111.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
