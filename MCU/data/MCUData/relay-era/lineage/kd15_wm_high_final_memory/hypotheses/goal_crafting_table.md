# goal_crafting_table

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2400
- depends_on: goal_mine_log, resource_reset_three_logs

## Statement

The current reset crafted the table at step 1428; it was placed adjacent to (-2998.72,64,-5563.26) at step 2077 and remained open through step 2155.

## Evidence

- At step 603 craft_item spruce_planks +4 fired, and at step 606 INV spruce_planks +4 verified that the output was banked in slot 1.
- events/events.jsonl records milestone crafting_table and craft_item crafting_table +1 at step 638; the live GUI remains open immediately after the interrupted cursor-to-slot action.
- events/events.jsonl verifies the milestone and craft_item at 638; [INV] crafting_table +1 at 642 and step_1200.png shows it in hotbar slot 1.
- The current event stream is empty, the header is 0/24, and the hotbar is empty at step 600.
- events/events.jsonl has no craft_item events through step 1200; pickup spruce_log +1 fired at step 661 and step_1200.png shows that single log in hotbar slot 0.
- events/events.jsonl records milestone crafting_table and craft_item crafting_table +1 at step 1428; live GRID showed the complete 2x2 recipe and output before the successful output click.
- events/events.jsonl records the crafting_table milestone and craft_item at 1428; logs.txt records [INV] crafting_table +1 at 1433; frame 1800 shows it in slot 0.
- events verifies craft/milestone at 1428; logs records crafting_table -1 at placement step 2077 and the table GUI open through 2155.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
