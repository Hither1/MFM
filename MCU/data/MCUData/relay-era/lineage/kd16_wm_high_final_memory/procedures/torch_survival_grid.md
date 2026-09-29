# torch_survival_grid
Preconditions: survival inventory open; coal and sticks available; an existing torch stack is preferably in zero-based hotbar slot 8.

1. Move the coal stack to `2x2` cell 0 and place it.
2. Move the stick stack to `2x2` cell 2 and place it. `[GRID]` must report cells `[0,2] out=FULL`.
3. `cursor_to_cell(grid="2x2", cell="out")`, then `gui_click()` takes one batch of four torches. With two coal and two sticks, repeat once while output remains FULL.
4. `cursor_to_slot(slot=8)`, then `gui_click()` banks/merges the torch stack into hotbar slot 9.
5. Close only after `[GRID]` cells are empty and `[CURSOR]` reports nothing off-inventory.

Verified: `craft_item torch +4` at step 10499 and `torch +4` inventory at step 10503. A premature close was refused because one coal/stick pair remained in the grid; take the still-FULL output before closing.
