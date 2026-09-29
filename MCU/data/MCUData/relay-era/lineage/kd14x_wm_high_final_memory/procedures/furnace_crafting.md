# furnace_crafting
Preconditions: 8 cobblestone plus a free player slot; 3x3 crafting-table screen open.
1. In one submitted plan, `cursor_to_slot(cobble_slot)` then `gui_click`; require the cobble stack on the cursor.
2. For cells 0, 1, 2, 3, 5, 6, 7, 8, pair `cursor_to_cell(grid="3x3",cell=N)` with `gui_right_click()`; leave cell 4 empty.
3. Return the remainder to its player slot. Require `[GRID]` edge cells occupied and `out=FULL`.
4. Pair `cursor_to_cell(grid="3x3",cell="out")` with `gui_click()`. If no craft event fires, re-land and click once; do not infer success from the frame.
5. Require `craft_item furnace`, land on a free player slot, `gui_click`, and require `[INV] furnace +1` before closing.

Current-run evidence: cobble x41 lifted at 6531; eight edge cells filled and x33 banked at 6580; first output click at 6586 produced no event; re-land+click fired `craft_item furnace` at 6588; slot 8 banking produced `[INV] furnace +1` at 6594.

Failure/quirk: the cursor parser retained stale `cobblestonex8` after the recipe grid was consumed and the furnace was banked. Trust the craft event, empty grid, and inventory delta together; never force-close on a stale label until those three agree.
