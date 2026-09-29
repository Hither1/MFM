# sticks
Preconditions: survival inventory screen open; at least two planks in one player inventory stack.

1. `cursor_to_slot(slot=0)`, `gui_click()` lifted the plank stack; verify `[INV] spruce_planks -N` rather than trusting the stale cursor item label.
2. `cursor_to_cell(grid="2x2", cell=0)`, `gui_right_click()` placed one plank in the upper-left cell.
3. `cursor_to_cell(grid="2x2", cell=2)`, `gui_right_click()` placed one plank directly below it; `[GRID] 2x2 cells [0,2] out=FULL` verified the recipe.
4. `cursor_to_slot(slot=0)`, `gui_click()` banked the remaining planks before collecting output; `[INV] spruce_planks +2` verified this.
5. `cursor_to_cell(grid="2x2", cell="out")`, `gui_click()` took four sticks and cleared the relevant 2x2 grid; `craft_item stick +4` fired at step 1842.
6. `cursor_to_slot(slot=4)`, `gui_click()` banked the output; `[INV] stick +4` at step 1846 verified safe storage.

Observed quirk: `[CURSOR]` continued to report `spruce_logx1` throughout, but stat, inventory, and relevant grid transitions were internally consistent and proved the label stale.
