# goal_iron_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 10860
- depends_on: goal_iron_ingot, goal_crafting_table, resource_iron_ore_drop_6296, location_current_ascent_8208, location_current_surface_furnace_8528, mechanism_foreground_tree_ray_9538, location_live_table_2077, location_table_east_bank_10681

## Statement

The current reset crafted the iron pickaxe at step 10860; the environment milestone and craft_item statistic both verified it, and the output is being banked into zero-based hotbar slot 3 before leaving the table.

## Evidence

- events/events.jsonl records mine_block spruce_log at 9946 and pickup spruce_log at 9956; current inventory reports spruce_log x1, iron_ore x2, and iron_ingot x1.
- events record craft_item spruce_planks +4 at step 9980 and craft_item stick +4 at step 10012; authoritative state at step 10019 reports planks x2 and sticks x4, while close_inventory was refused because CURSOR still reports spruce_log x1.
- At steps 10025-10034 the 2x2 grid was empty after output interaction and no new craft occurred; at step 10037 gui_click on hotbar slot 3 produced the decisive real delta spruce_planks -2, while the cursor parser continued reporting stale spruce_logx1. Current inventory still has iron_ingot x1, iron_ore x2, and sticks x4.
- events verify spruce-log break/pickup 9946/9956, plank craft 9980, stick craft 10012, and no iron-pick craft through 10138; inventory deltas bank planks x2 at 10043 and the live pose is 1.6 blocks from the furnace.
- At steps 10204 and 10217, iron_ore -2 and spruce_planks -2 prove both stacks were lifted; furnace GRID showed [in,fuel,out] at 10222 and still does at 10422 after a 200-tick wait.
- events/events.jsonl records craft_item iron_ingot +2 at step 10630; logs at step 10634 record [INV] iron_ingot +2; live STATE reports iron_ingot x3 and stick x4.
- craft_item iron_ingot +2 fired at 10630; the latest hotbar shows three ingots/four sticks, and frame step_10738 plus map pose (-2995.97,65,-5563.39) show the table directly ahead. No craft_item iron_pickaxe exists.
- events/events.jsonl records milestone iron_pickaxe and craft_item iron_pickaxe +1 at step 10860; the live 3x3 grid is empty immediately after output extraction.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
