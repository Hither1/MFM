# mechanism_gui_cursor_stale_consumed_items

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 9000
- updated_step: 1800

## Statement

After a recipe grid clears, CURSOR/force-close summaries may still name banked or consumed ingredients; current events, INV, the active GRID, and matching frames outrank that phantom aggregate.

## Evidence

- Ore/plank labels persisted after furnace consumption and craft_item iron_ingot +2, whereas the table/dirt swap at 8998 produced matching INV deltas and a visibly attached dirt stack.
- Iron ore remained in CURSOR text from 5899 through 6410 even though furnace output completed at 6107 and the third ingot entered inventory at 6111; repeated redeposit/close attempts changed no inventory.
- At 5995 the furnace ring cleared, craft_item furnace fired at 5997, and cobble x40 was already back in inventory, yet CURSOR continued to report cobblestone x8 through step 6000.
- The step-1494 force-close note claimed planks x3/sticks x2 were dropped, yet frames 1494 and 1800 show both stacks banked and no pickup events were required.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
