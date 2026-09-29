# goal_stone_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 3600
- depends_on: goal_mine_cobblestone, goal_crafting_table, mechanism_gui_cursor_recenter_3997, mechanism_pillar_ceiling_clearance_3000, location_table_placement_ray_1403, location_live_surface_table_ep0000_1157

## Statement

The live reset crafted the stone pickaxe at step 3340 and banked it in zero-based hotbar slot 5 at step 3345; it is carried and unused at step 3600.

## Evidence

- Current events contain no craft_item stone_pickaxe.
- The milestone header is 4/24 and events contain no craft_item stone_pickaxe; step-2400 accounting shows cobblestone x26 and sticks x2.
- The live milestone header is 4/24 and events/events.jsonl ends at step 2993 with no craft_item stone_pickaxe; step_3000.png and current event accounting show cobblestone x25 and sticks x2 at y63.
- At step 3178, jump-use consumed three cobblestone and moved the player from y64 to y68. Live state reports cobblestone x21, sticks x2, and the attached downward frame visibly includes the crafting table at lower left.
- Step 3239 use_until_gui opened nothing at the drifted pose while the table is visibly nearby; current inventory still contains all recipe ingredients and an empty destination slot.
- At step 3280 use_until_gui changed GUI open from false to true and the attached frame shows the crafting-table screen. At step 3283 cursor_to_slot reached hotbar slot 4, but current inventory still has cobblestone x21 and off-inventory is empty, proving the subsequent lift did not occur.
- events/events.jsonl records milestone stone_pickaxe and craft_item stone_pickaxe +1 at step 3340; logs Action 210 shows the cursor landed over hotbar slot 5 immediately afterward.
- events/events.jsonl records milestone and craft_item stone_pickaxe at 3340; logs records INV stone_pickaxe +1 at 3345; step_3600.png shows it in slot 5.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
