# goal_crafting_table

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 600
- depends_on: goal_mine_log, resource_early_logs, resource_live_early_logs

## Statement

The crafting_table milestone fired at live step 591, and [INV] crafting_table +1 plus frame 600 prove the table is safely banked in hotbar slot 1 by step 595.

## Evidence

- Step 795 STATE reports GUI open, 2x2 cells [0,1,2,3], out=FULL, and one spruce log off-inventory on the cursor; inventory retains two further spruce logs.
- events/events.jsonl records both milestone crafting_table and craft_item crafting_table +1 at step 797.
- The live step-533 header reports only mine_log verified. Three spruce logs are available on the GUI cursor, enough to craft planks and then a table while retaining two logs.
- Live events verify craft_item spruce_planks +4 at step 555, and step 559 [INV]/STATE verify spruce_planks x4 in hotbar slot 1 with the survival inventory GUI open and the authoritative 2x2 grid empty.
- events/events.jsonl verifies craft_item spruce_planks +4 at step 555; logs at step 559 verify spruce_planks +4 in hotbar slot 1, and step 562 verifies [INV] spruce_planks -4 while the survival GUI stays open, proving the stack was lifted despite the stale spruce-log cursor label.
- At live step 583, [GRID] reports 2x2 cells [0,1,2,3] out=FULL; the frame visibly shows four spruce planks in the table recipe and STATE lists spruce_logx2 banked in hotbar slot 0.
- events/events.jsonl records both milestone crafting_table and craft_item crafting_table +1 at step 591; the live GUI remains open and no [INV] crafting_table +1 has yet appeared.
- Current events lines 8-9 verify the milestone/craft at 591; logs record the inventory increase at 595; frame 600 shows the table in slot 1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
