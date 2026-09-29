# goal_crafting_table

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1800
- depends_on: goal_mine_log, resource_early_logs, resource_live_early_logs

## Statement

The crafting-table milestone was environment-confirmed at step 1131; the sole table is now placed this run at block centre (-3007.5,69.5,-5566.5).

## Evidence

- Only mine_log is verified; no craft event exists through step 1200, while pickup spruce_log +1 at step 1001 supplies the exact table input.
- events/events.jsonl records milestone crafting_table and craft_item crafting_table +1 at step 1272; the GUI remains open at the output-stow stage.
- events/events.jsonl lines 12-13 verify milestone/craft at 1272; logs record [INV] crafting_table +1 at 1278; frame 1800 shows it banked.
- Through step 600 events contain only mine_log/mine_block spruce_log at 480, with no pickup or craft_item event; the hotbar is empty.
- At step 1123 the active survival-screen GRID reports cells [0,1,2,3] and out=FULL; spruce planks were event-confirmed at step 1095 and consumed from inventory while laying out the recipe.
- events/events.jsonl records both the crafting_table milestone and craft_item crafting_table +1 at step 1131; the authoritative active 2x2 grid is empty after the output was taken.
- events/events.jsonl lines 8-9 record the milestone and craft_item crafting_table at step 1131; logs record [INV] crafting_table +1 at 1137, and the enlarged step-1200 hotbar visibly contains the table.
- events lines 8-9 verify milestone/craft at 1131; logs show table INV -1 and use_item crafting_table at 1256, with no later table mine/pickup event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
