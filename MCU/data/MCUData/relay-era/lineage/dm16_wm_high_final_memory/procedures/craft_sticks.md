# craft_sticks
Preconditions: survival inventory open; at least 2 planks in one inventory slot; cursor empty.
1. `cursor_to_slot(slot=2)`, then `gui_click()` lifted the four-plank stack; `[INV] spruce_planks -4` verified the lift.
2. `cursor_to_cell(grid="2x2", cell=0)`, then `gui_right_click()` placed one plank in the upper-left cell.
3. `cursor_to_cell(grid="2x2", cell=2)`, then `gui_right_click()` placed one plank directly below it; `[GRID] 2x2 cells [0,2] out=FULL` verified the recipe.
4. `cursor_to_slot(slot=2)`, then `gui_click()` returned the two excess planks; `[INV] spruce_planks +2` verified the deposit.
5. `cursor_to_cell(grid="2x2", cell="out")`, then `gui_click()` collected the output. `cursor_to_slot(slot=1)`, then `gui_click()` deposited it.
6. `events/events.jsonl` verified `craft_item stick +4` at step 971, and step 975 inventory reported `stickx4`.

Observed quirk: the cursor tracker retained a stale `spruce_logx2` off-inventory label throughout, so recipe-grid occupancy plus `[INV]` and event evidence were authoritative.
