# goal_furnace

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 6600
- depends_on: goal_mine_cobblestone, goal_crafting_table, goal_stone_pickaxe, mechanism_dirt_pillar_return_2325, mechanism_gui_cursor_recenter_3997

## Statement

The current reset crafted a furnace at step 6588 and banked it in zero-based hotbar slot 8 at step 6594; the GUI closed at 6597 and the furnace milestone is fully secured.

## Evidence

- No craft_item furnace exists through step 6000; event accounting gives cobblestone x45 and step 5994 verifies the first return-pillar placement.
- Step 6058 records the fifth east-shaft cobblestone placement; step 6101 authoritative state is (-2999.35,49.20,-5576.69) after a 13.05-block west traversal, with cobblestone x41 and no craft_item furnace event.
- Steps 6103-6375 record the main-shaft pillar from stable y49 to y67; go_to then advanced 7.07 blocks and live state at step 6403 is surface y69 near the known table pose.
- Action 359 ended at step 6518 with [GUI] open=True at (-3003.78,68,-5567.95), empty cursor/grid contents, and cobblestone x41 in zero-based hotbar slot 1.
- Action 361 at step 6524 reported the pointer 86 px from its prior landing and lifted nothing, while GUI open=True and inventory remained cobblestone x41. The established recenter mechanism says landing and click must be paired within one plan.
- Step 6531 reports [INV] cobblestone -41 and [CURSOR] cobblestonex41 after same-plan cursor_to_slot(1)+gui_click; the crafting-table GUI remains open.
- At step 6588 events recorded craft_item furnace +1 and MILESTONE furnace verified; the 3x3 grid became empty while the cursor tracker retained its documented stale cobblestone x8 label.
- events records MILESTONE/craft_item furnace at 6588; logs records [INV] furnace +1 at 6594 and GUI open=False at 6597.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
