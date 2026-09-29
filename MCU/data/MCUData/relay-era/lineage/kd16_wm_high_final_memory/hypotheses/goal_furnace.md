# goal_furnace

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 3600
- depends_on: goal_mine_cobblestone, goal_crafting_table, goal_stone_pickaxe, mechanism_dirt_pillar_return_2325, mechanism_gui_cursor_recenter_3997, location_live_surface_table_ep0000_1157

## Statement

The live reset crafted the furnace at step 3407 and banked it in zero-based hotbar slot 6 at step 3411; it remains carried and unplaced at step 3600.

## Evidence

- Action 361 at step 6524 reported the pointer 86 px from its prior landing and lifted nothing, while GUI open=True and inventory remained cobblestone x41. The established recenter mechanism says landing and click must be paired within one plan.
- Step 6531 reports [INV] cobblestone -41 and [CURSOR] cobblestonex41 after same-plan cursor_to_slot(1)+gui_click; the crafting-table GUI remains open.
- At step 6588 events recorded craft_item furnace +1 and MILESTONE furnace verified; the 3x3 grid became empty while the cursor tracker retained its documented stale cobblestone x8 label.
- events records MILESTONE/craft_item furnace at 6588; logs records [INV] furnace +1 at 6594 and GUI open=False at 6597.
- Current events contain no craft_item furnace.
- Current events contain no craft_item furnace; cobblestone x26 is sufficient for ascent reserve plus both recipes.
- events/events.jsonl records both milestone furnace and craft_item furnace +1 at step 3407; the 3x3 grid is empty after ingredient consumption, live inventory has the exact expected 10 cobblestone and no sticks, and frame step_3407 visibly shows the furnace output on the cursor over empty slot 6.
- events/events.jsonl records milestone and craft_item furnace at 3407; logs records INV furnace +1 at 3411; no use_item furnace follows and step_3600.png shows it in slot 6.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
