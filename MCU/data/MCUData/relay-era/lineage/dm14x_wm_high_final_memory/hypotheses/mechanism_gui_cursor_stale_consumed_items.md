# mechanism_gui_cursor_stale_consumed_items

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 9000
- updated_step: 6600

## Statement

After active furnace GRID empties and craft_item proves consumption, a lingering ingredient in CURSOR text is phantom; inventory deltas and events outrank it.

## Evidence

- Ore/plank labels persisted after furnace consumption and craft_item iron_ingot +2, whereas the table/dirt swap at 8998 produced matching INV deltas and a visibly attached dirt stack.
- Iron ore remained in CURSOR text from 5899 through 6410 even though furnace output completed at 6107 and the third ingot entered inventory at 6111; repeated redeposit/close attempts changed no inventory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
