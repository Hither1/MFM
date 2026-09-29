# stone_pickaxe
Preconditions: crafting-table 3x3 screen open; at least 3 cobblestone, 2 sticks, and one empty player slot for the output.

1. `cursor_to_slot(slot=1)`, `gui_click()` lifted the cobblestone stack.
2. For cells 0, 1, and 2: `cursor_to_cell(grid="3x3", cell=N)`, `gui_right_click()` placed one cobblestone across the top row.
3. `cursor_to_slot(slot=1)`, `gui_click()` banked the cobblestone remainder.
4. `cursor_to_slot(slot=2)`, `gui_click()` lifted the sticks.
5. For cells 4 and 7: `cursor_to_cell(grid="3x3", cell=N)`, `gui_right_click()` placed the vertical handle.
6. `cursor_to_slot(slot=2)`, `gui_click()` banked the stick remainder; `[GRID] 3x3 ... out=FULL` confirmed the recipe.
7. `cursor_to_cell(grid="3x3", cell="out")`, `gui_click()` took the output and produced `craft_item stone_pickaxe +1` at step 4166.
8. Re-land with `cursor_to_slot(slot=0)`, then `gui_click()` to bank the output in the empty slot.

Observed failure mode: cursor position can recenter between turns. Always pair each `cursor_to_*` with its click in the same action plan. The off-inventory summary can list grid ingredients without identifying the cursor-held output, so use the craft event plus the known empty destination slot.
