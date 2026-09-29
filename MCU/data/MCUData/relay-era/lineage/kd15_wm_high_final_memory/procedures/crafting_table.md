# crafting_table

Preconditions: survival inventory open; four planks in a player slot; empty player slot for output.

1. In the current reset, `cursor_to_slot(slot=0)`, `gui_click()` lifted four banked planks; `[INV] spruce_planks -4` at step 1399 verified the lift.
2. For cells 0, 1, 2, 3: `cursor_to_cell(grid="2x2",cell=N)`, then `gui_right_click()` placed one plank. `[GRID]` showed all four occupied and `out=FULL`.
3. `cursor_to_cell(grid="2x2",cell="out")`, `gui_click()` took the output. `events/events.jsonl` records `craft_item crafting_table +1` and the milestone at step 1428.
4. Re-land on empty hotbar slot 0 and `gui_click()`; `[INV] crafting_table +1` at step 1433 verified banking.
5. Before closing, obey the runner even if `[CURSOR]` names an impossible stale stack: use `stow_items(grid="2x2",cells=[])` or explicitly bank anything reported off-inventory. Never force-close.

Observed quirk: `[CURSOR]` remained labeled `spruce_logx1` after the log had been event-verifiably converted and the table banked. The later force-close emitted an item-entity warning, so stale-looking labels are not safe to ignore.
