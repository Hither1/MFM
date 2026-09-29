# furnace
Preconditions: at least 8 cobblestone in inventory; adjacent crafting-table screen open.
1. `cursor_to_slot(slot=6)`, then `gui_click()` lifted the cobblestone stack used in this run.
2. For 3x3 cells `0,1,2,3,5,6,7,8`, `cursor_to_cell(grid="3x3", cell=N)` followed by `gui_right_click()` placed one cobblestone around the perimeter.
3. `cursor_to_slot(slot=6)`, then `gui_click()` returned the nine-block remainder before taking the output; `[GRID] ... out=FULL` confirmed the ring.
4. `cursor_to_cell(grid="3x3", cell="out")`, then `gui_click()` cleared the recipe and produced `craft_item furnace +1` plus the milestone at step 3798.
5. The cursor tracker continued to report the consumed grid cobblestone aggregate after the output click; trust the cleared 3x3 grid and craft event, then deposit the furnace in an empty inventory slot before closing.
