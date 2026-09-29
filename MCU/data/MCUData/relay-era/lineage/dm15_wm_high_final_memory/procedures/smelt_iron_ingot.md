# smelt_iron_ingot
Preconditions: one iron ore, one plank, placed furnace, player adjacent, furnace screen open, cursor empty.
1. Lift the ore from its inventory slot; `cursor_to_cell(grid="furnace", cell=0)`, then `gui_click()` deposits it.
2. Lift the plank stack; `cursor_to_cell(grid="furnace", cell=1)`, then `gui_right_click()` places exactly one fuel; return the remainder to its inventory slot.
3. Wait 200 ticks. Furnace GRID changes to `[out]` when smelting completes.
4. `cursor_to_cell(grid="furnace", cell="out")`, then `gui_click()` takes the ingot; deposit it into an empty inventory slot.
5. Taking and stowing the furnace output produced `craft_item iron_ingot +1` and `INV iron_ingot +1`, but not the pickup milestone. To trigger `pickup`, lift the ingot, `close_inventory(force=true)` to drop it at the player's feet, and wait about 30 ticks to recollect it.

Observed quirk: the cursor tracker continued listing consumed iron ore and plank after furnace GRID became empty. Trust furnace GRID, inventory deltas, and events.
