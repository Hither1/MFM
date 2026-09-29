# goal_wooden_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1200
- depends_on: goal_crafting_table, resource_early_logs, resource_live_early_logs

## Statement

The wooden_pickaxe milestone was verified at live step 781, and the crafted tool was safely deposited into hotbar slot 1 at step 786; it is selected and usable at step 1200.

## Evidence

- Step 968 landed over hotbar slot 2, but by step 971 the pointer had reset to (88,83); the guard explicitly directs re-landing immediately before clicking. STATE still verifies spruce_planks x6 and stick x4.
- Step 978 [CURSOR] reports spruce_planksx6 over hotbar slot 2 and [INV] reports spruce_planks -6; the 3x3 table screen remains open.
- Step 1001 authoritative GRID reports 3x3 cells [0,1,2], cursor has no loose stack, and INV reports spruce_planks +3.
- events/events.jsonl records both MILESTONE wooden_pickaxe and craft_item wooden_pickaxe +1 at step 1030; the 3x3 grid then cleared and the cursor landed over hotbar slot 0.
- Current events contain no wooden_pickaxe event; header says it is first unmet, while frame 600 shows the required wood/table resources.
- Live STATE at 711 lists spruce_planks x6 and stick x4; [INV] crafting_table -1 and the frame verify the table was placed directly ahead.
- events/events.jsonl records both the wooden_pickaxe milestone and craft_item wooden_pickaxe at step 781; the active 3x3 GRID is empty and the attached frame shows the crafted pickaxe attached to the cursor over hotbar slot 1.
- Current-run events record milestone/craft_item wooden_pickaxe at 781; logs record INV wooden_pickaxe +1 at 786; frame 1200 shows it selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
