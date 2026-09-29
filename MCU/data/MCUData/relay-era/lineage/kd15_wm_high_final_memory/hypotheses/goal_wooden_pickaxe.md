# goal_wooden_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2155
- depends_on: goal_crafting_table, resource_three_logs, resource_reset_three_logs

## Statement

The current reset crafted a wooden pickaxe at step 2148 and banked it in zero-based hotbar slot 0 at step 2152; both the craft_item statistic, environment milestone, and inventory transfer are verified. The active 3x3 table grid is empty, while the off-inventory warning is caused by irrelevant 2x2-grid visual noise.

## Evidence

- No wooden_pickaxe craft event exists. The current inventory has one log only, which is exactly consumed by the cheaper crafting-table milestone.
- No wooden_pickaxe craft event exists through step 1651. Current state has the table and one log, and the adjacent spruce produced a verified log break/pickup at steps 1513/1523.
- No wooden_pickaxe craft event exists through 1800. Frame 1800 shows table x1, log x1, and bark centered at close range.
- No wooden_pickaxe craft event exists through step 1896. Live inventory has table x1 and log x1, while the current frame has dirt—not bark—under the crosshair.
- At step 1976 the live inventory is crafting_table x1 and spruce_log x2; no wooden_pickaxe craft event exists yet.
- Events verify two spruce-plank crafts at steps 2007 and 2030 and a stick craft at 2062; live step-2077 inventory is spruce_planks x6 and stick x4, while [INV] crafting_table -1 and the attached frame verify the table was placed directly under the crosshair.
- events/events.jsonl records milestone wooden_pickaxe and craft_item wooden_pickaxe +1 at step 2148; the attached frame shows the wooden-pickaxe icon on the cursor over hotbar slot 0, while the relevant 3x3 grid is empty after output extraction.
- events/events.jsonl verifies the milestone and craft_item at step 2148; logs.txt records [INV] wooden_pickaxe +1 at step 2152 and the active 3x3 grid as empty through step 2155, while live inventory lists wooden_pickaxe x1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
