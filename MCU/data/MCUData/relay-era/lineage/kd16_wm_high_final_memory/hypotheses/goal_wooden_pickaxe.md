# goal_wooden_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1224
- depends_on: goal_crafting_table, resource_three_logs, resource_reset_three_logs, state_current_pick_recipe_1200

## Statement

The live reset crafted a wooden pickaxe at step 1224; the environment milestone and craft_item event are verified, and the cursor-held output is being banked into zero-based hotbar slot 2.

## Evidence

- events/events.jsonl records craft_item spruce_planks +4 at steps 1293 and 1319; live inventory still lists only the first spruce_planks x4 stack while the relevant 2x2 grid is empty, identifying the second output as the unbanked stack despite the stale cursor item label.
- craft_item spruce_planks fired at steps 1293 and 1319; step 1326 reports spruce_planks x8 banked and spruce_log x2 off-inventory.
- events verify spruce_planks +4 at steps 1293 and 1319; logs.txt records [INV] spruce_planks -8 at step 1337 while the survival inventory remains open.
- At step 1421 GUI open=True; inventory reports spruce_planks x6 and stick x4, and use_item crafting_table was event-verified at step 1411.
- events/events.jsonl records milestone wooden_pickaxe and craft_item wooden_pickaxe at step 1480; live [CURSOR] is over hotbar slot 3 immediately after output extraction.
- Current events contain no craft_item wooden_pickaxe and the step-600 hotbar contains only one log.
- No wooden_pickaxe craft event exists through step 1200. Logs verify plank placement and banking through 1195; the live frame shows three top-row planks producing six slabs and the cursor over the banked sticks.
- At step 1224 the harness reports 3/24, MILESTONE wooden_pickaxe verified, and craft_item wooden_pickaxe +1; [CURSOR] is over empty hotbar slot 2 and the frame shows the wooden-pickaxe icon on the cursor.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
