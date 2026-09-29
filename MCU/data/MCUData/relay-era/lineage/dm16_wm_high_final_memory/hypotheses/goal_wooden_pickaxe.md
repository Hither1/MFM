# goal_wooden_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1800
- depends_on: goal_crafting_table, resource_early_logs, resource_live_early_logs, location_adjacent_spruce_face_924, location_live_table_1252

## Statement

The wooden-pickaxe milestone was environment-confirmed at step 1323, and the tool is securely banked in zero-based hotbar slot 0 through step 1800.

## Evidence

- The live header reports only 1/10 and events through step 600 contain no wooden_pickaxe craft.
- No wooden_pickaxe event exists through events line 12. Plank crafts fired at 1095/1156/1168, stick craft at 1200, and the magnified step-1200 frame shows table x1, planks x6, sticks x4 on the pointer, and an empty 2x2 grid.
- At step 1204 [INV] stick +4 fired; frame 1214 shows table x1, planks x6, sticks x4 in the hotbar and an empty active 2x2 grid. procedures/craft_wooden_pickaxe.md explicitly documents this stale off-inventory-label case as safe for forced close.
- At step 1247 STATE lists crafting_table x1, spruce_planks x6, and stick x4 with GUI closed. Steps 1229 and earlier placement attempts caused neither use_item nor an inventory decrement; the current pitch-80 frame centers near-underfoot grass, consistent with collision-invalid placement.
- Step 1252 records crafting_table -1 and step 1259 records GUI open=True with use_item crafting_table; authoritative STATE lists spruce_planks x6 and sticks x4.
- At step 1299 the active 3x3 GRID has cells 0,1,2 occupied and [INV] stick -4 confirms the stick stack was lifted from hotbar slot 1.
- events/events.jsonl records both MILESTONE wooden_pickaxe and craft_item wooden_pickaxe at step 1323; the active 3x3 grid is empty and the attached frame visibly shows the pickaxe at the cursor over hotbar slot 0.
- events lines 14-15 verify milestone/craft at 1323; INV wooden_pickaxe +1 fired at 1328 and frame 1800 visibly shows the selected pick in slot 0.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
