# goal_wooden_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1480
- depends_on: goal_crafting_table, resource_three_logs, resource_reset_three_logs

## Statement

The current reset crafted a wooden pickaxe at step 1480; both the craft_item statistic and the environment milestone verified it, and the output is currently held by the GUI cursor over empty zero-based hotbar slot 3.

## Evidence

- The milestone list is 2/24 with wooden_pickaxe unmet; no craft event exists, and step_1200.png shows only one log plus the table.
- At step 1250 a nearby spruce log broke; at step 1262 pickup spruce_log +1 raised the authoritative inventory to spruce_log x2 alongside the banked crafting table.
- events/events.jsonl records craft_item spruce_planks +4 at step 1293; step 1294 has an empty relevant 2x2 grid, one banked spruce log, and the crafted output at the cursor.
- events/events.jsonl records craft_item spruce_planks +4 at steps 1293 and 1319; live inventory still lists only the first spruce_planks x4 stack while the relevant 2x2 grid is empty, identifying the second output as the unbanked stack despite the stale cursor item label.
- craft_item spruce_planks fired at steps 1293 and 1319; step 1326 reports spruce_planks x8 banked and spruce_log x2 off-inventory.
- events verify spruce_planks +4 at steps 1293 and 1319; logs.txt records [INV] spruce_planks -8 at step 1337 while the survival inventory remains open.
- At step 1421 GUI open=True; inventory reports spruce_planks x6 and stick x4, and use_item crafting_table was event-verified at step 1411.
- events/events.jsonl records milestone wooden_pickaxe and craft_item wooden_pickaxe at step 1480; live [CURSOR] is over hotbar slot 3 immediately after output extraction.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
