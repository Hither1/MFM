# iron_pickaxe
Preconditions: crafting-table 3x3 screen open; 3 iron ingots, at least 2 sticks, and one empty inventory slot.

1. Lift the ingot stack, then pair `cursor_to_cell(grid="3x3", cell=N)` with `gui_right_click()` for cells 0, 1, 2.
2. Lift sticks and right-click cells 4 and 7; bank any stick remainder. `[GRID] ... out=FULL` confirms the layout.
3. `cursor_to_cell(grid="3x3", cell="out")`, `gui_click()` takes the output. At current-reset step 7905 this fired `craft_item iron_pickaxe +1` and the milestone.
4. Land on an empty player slot and `gui_click()` to bank the cursor-held pick before closing. Current-reset step 7910 banked it in zero-based hotbar slot 5 (`[INV] iron_pickaxe +1`).

Failure guard: an empty 3x3 grid plus the craft event proves ingredients were consumed even if the aggregate off-inventory label still names them. Do not close until the output has been clicked into a player slot; once banked, a force-close can clear only that stale label.
