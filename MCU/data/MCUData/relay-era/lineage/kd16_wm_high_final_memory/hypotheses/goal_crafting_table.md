# goal_crafting_table

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1200
- depends_on: goal_mine_log, resource_reset_three_logs

## Statement

The live reset crafted the table at step 1045, banked it at 1049, placed it at the current surface worksite at 1153, and opened its GUI at 1157.

## Evidence

- The environment reports crafting_table unmet; events through step 580 contain no craft_item event, while step 443 records pickup spruce_log +2 and step 580 shows that stack lifted on the survival-inventory cursor.
- events/events.jsonl has no craft_item event; step-597 GRID and step-600 frame show cell 0 occupied and output full.
- At step 603 craft_item spruce_planks +4 fired, and at step 606 INV spruce_planks +4 verified that the output was banked in slot 1.
- events/events.jsonl records milestone crafting_table and craft_item crafting_table +1 at step 638; the live GUI remains open immediately after the interrupted cursor-to-slot action.
- events/events.jsonl verifies the milestone and craft_item at 638; [INV] crafting_table +1 at 642 and step_1200.png shows it in hotbar slot 1.
- Environment progress is 1/24 with crafting_table first unmet, and current events contain no craft_item entry.
- events/events.jsonl records the crafting_table milestone and craft_item crafting_table +1 at step 1045; the current survival inventory screen remains open for safe output banking.
- events/events.jsonl verifies the milestone and craft_item at 1045 and use_item crafting_table at 1157; logs record [INV] crafting_table +1 at 1049 and -1 on placement at 1153.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
