# stone_pickaxe
Preconditions: three cobblestone and two sticks in inventory; the 3x3 crafting-table screen is open; destination hotbar slot 1 is empty.

1. `cursor_to_slot(slot=6)`, `gui_click()` lifted the three-cobblestone stack (verified by `[INV] cobblestone -3`).
2. For cells 0, 1, and 2: `cursor_to_cell(grid="3x3", cell=N)`, then `gui_right_click()` placed one cobblestone across the top row.
3. `cursor_to_slot(slot=1)`, `gui_click()` lifted two sticks (verified by `[INV] stick -2`).
4. For cells 4 and 7: `cursor_to_cell(grid="3x3", cell=N)`, then `gui_right_click()` placed the handle.
5. `cursor_to_cell(grid="3x3", cell="out")` landed on an `out=FULL` recipe; `gui_click()` produced `craft_item stone_pickaxe +1` and the milestone at step 3066.
6. In this run, `cursor_to_slot(slot=3)`, then a separate `gui_click()` stowed the pickaxe in hotbar slot 4 and produced `[INV] stone_pickaxe +1` at step 3071.

Observed detail: the aggregate off-inventory list continued to name cobblestone and sticks after the output cleared the real 3x3 grid and the pickaxe was stowed. Rely on `[GRID]`, the craft event, and the inventory delta. With the real grid and cursor empty, `close_inventory(force=true)` safely bypasses this stale aggregate label.
