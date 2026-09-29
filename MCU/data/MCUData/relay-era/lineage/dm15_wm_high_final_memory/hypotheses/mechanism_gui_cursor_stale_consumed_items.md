# mechanism_gui_cursor_stale_consumed_items

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 9000
- updated_step: 6000

## Statement

After an active crafting/furnace grid clears and the craft event proves consumption, CURSOR may keep naming consumed ingredients; events, inventory deltas, and the active grid outrank that phantom label.

## Evidence

- Ore/plank labels persisted after furnace consumption and craft_item iron_ingot +2, whereas the table/dirt swap at 8998 produced matching INV deltas and a visibly attached dirt stack.
- Iron ore remained in CURSOR text from 5899 through 6410 even though furnace output completed at 6107 and the third ingot entered inventory at 6111; repeated redeposit/close attempts changed no inventory.
- At 5995 the furnace ring cleared, craft_item furnace fired at 5997, and cobble x40 was already back in inventory, yet CURSOR continued to report cobblestone x8 through step 6000.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
