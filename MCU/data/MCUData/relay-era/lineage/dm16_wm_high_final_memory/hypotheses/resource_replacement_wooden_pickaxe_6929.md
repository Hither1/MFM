# resource_replacement_wooden_pickaxe_6929

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 6929
- updated_step: 7200
- depends_on: resource_respawn_rebuild_6248, location_table_reapproach_6921, goal_wooden_pickaxe, goal_crafting_table

## Statement

Refuted as cross-trajectory contamination: no wooden pickaxe was crafted or stowed at steps 6994/6998 in the current prefix.

## Evidence

- Authoritative step-6929 inventory lists spruce_planksx6 in hotbar slot 0 and stickx4 in slot 1; the proven procedures/craft_wooden_pickaxe.md sequence uses three planks and two sticks.
- At step 6942, gui_click produced [INV] spruce_planks -6 and [CURSOR] spruce_planksx6 over hotbar slot 0 while the authoritative open 3x3 row had no occupied cells.
- At step 6965, [GRID] authoritatively reports 3x3 cells [0,1,2] and [INV] reports spruce_planks +3, while live inventory shows spruce_planksx3 in hotbar slot 0 and stickx4 in slot 1.
- At step 6965 the authoritative 3x3 GRID reports cells [0,1,2] occupied and spruce_planks +3 returned to slot 0. At step 6970 gui_click reports [INV] stick -4 and the cursor report includes stickx4 over the now-empty hotbar slot 1.
- events/events.jsonl records craft_item wooden_pickaxe at step 6994; authoritative inventory at step 7124 lists wooden_pickaxe x1, spruce_planks x3, and stick x2 in hotbar slots 3, 1, and 2.
- craft_item wooden_pickaxe at 6994 and INV +1 at 6998 prove the tool; frame 7200 shows it. Forced-close note at 7127 contradicts only the old statement that remnants were banked.
- Current events at 6994/6998 contain no craft_item wooden_pickaxe; logs show the player stationary underground in the west tunnel.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
