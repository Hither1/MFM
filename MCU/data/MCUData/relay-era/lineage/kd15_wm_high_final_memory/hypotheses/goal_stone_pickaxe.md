# goal_stone_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 4800
- depends_on: goal_mine_cobblestone, goal_crafting_table, mechanism_gui_cursor_recenter_3997, mechanism_pillar_ceiling_clearance_3000, location_table_placement_ray_1403, location_current_dry_tunnel_4200

## Statement

The current reset crafted the stone pickaxe at step 4693 and banked it in zero-based hotbar slot 4; it is selected and unused at step 4800.

## Evidence

- Step 3237 reports cobblestone x5, dirt x2, sticks x2, wooden pickaxe x1 and no current craft_item stone_pickaxe event; the table placement at step 1408 was verified and the failed recovery attack at step 1563 broke no block.
- At step 3323 the live state reports the open table GUI and cobblestone x5/sticks x2; the prior click failed only because the cursor recentered between turns, and procedures/stone_pickaxe.md requires pairing each cursor landing with its click in one plan.
- At step 3377 events recorded craft_item stone_pickaxe +1 and the harness reports 5/24 with stone_pickaxe checked; the GUI remains open and player inventory has an empty slot 2.
- events/events.jsonl records milestone and craft_item stone_pickaxe at step 3377; logs record INV stone_pickaxe +1 at step 3381; step_3600.png shows the selected stone pick in slot 2.
- The current event stream is empty and the step-600 inventory has no tools.
- Current events through step 4200 contain no craft_item stone_pickaxe. Frame 4200 and inventory deltas verify cobblestone x12 at y57; the stale mark followed a productive 300-tick tunnel action that added nine cobblestone, not a failed prerequisite test.
- events/events.jsonl records MILESTONE stone_pickaxe and craft_item stone_pickaxe +1 at step 4693; current cursor is already over the empty destination slot.
- events/events.jsonl records milestone and craft_item stone_pickaxe at 4693; logs records INV stone_pickaxe +1 at 4698; frame 4800 shows it selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
