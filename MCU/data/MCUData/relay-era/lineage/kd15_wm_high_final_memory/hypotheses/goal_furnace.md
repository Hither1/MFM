# goal_furnace

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 4800
- depends_on: goal_mine_cobblestone, goal_crafting_table, goal_stone_pickaxe, mechanism_dirt_pillar_return_2325, mechanism_gui_cursor_recenter_3997, location_current_dry_tunnel_4200

## Statement

The current reset crafted the furnace at step 4761 and banked it in zero-based hotbar slot 5; it remains an unplaced inventory item at step 4800.

## Evidence

- Step 6531 reports [INV] cobblestone -41 and [CURSOR] cobblestonex41 after same-plan cursor_to_slot(1)+gui_click; the crafting-table GUI remains open.
- At step 6588 events recorded craft_item furnace +1 and MILESTONE furnace verified; the 3x3 grid became empty while the cursor tracker retained its documented stale cobblestone x8 label.
- events records MILESTONE/craft_item furnace at 6588; logs records [INV] furnace +1 at 6594 and GUI open=False at 6597.
- No craft_item furnace event exists and reset erased inherited workstations.
- No current craft_item furnace event exists. Step 4174 inventory shows enough cobblestone for furnace plus stone pick, and procedures/furnace_crafting.md preserves the verified GUI sequence.
- Current state has the table GUI open and cobblestone x11 in hotbar. The verified stone-pick recipe has consumed exactly three of the original fourteen cobble, preserving the eight needed for the furnace.
- events/events.jsonl records MILESTONE furnace and craft_item furnace +1 at step 4761; logs show the relevant 3x3 grid empty and the cursor landed over the intended empty hotbar destination after output extraction.
- events records milestone/craft_item furnace at 4761; logs records INV furnace +1 at 4765; frame 4800 shows the furnace in slot 5.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
