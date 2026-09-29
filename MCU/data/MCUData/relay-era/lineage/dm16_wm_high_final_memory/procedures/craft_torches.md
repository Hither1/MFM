# craft_torches
Preconditions: one coal or charcoal and at least one stick in inventory; survival inventory screen open.
1. `cursor_to_slot(slot=2)`, `gui_click()` lifted the fuel stack in the original run (use the live slot id).
2. `cursor_to_cell(grid="2x2", cell=0)`, `gui_click()` deposited coal/charcoal in the upper-left cell.
3. `cursor_to_slot(slot=1)`, `gui_click()` lifted four sticks.
4. `cursor_to_cell(grid="2x2", cell=2)`, `gui_right_click()` placed one stick directly below the charcoal.
5. `cursor_to_slot(slot=1)`, `gui_click()` returned the three spare sticks before collecting output; `[GRID] 2x2 cells [0,2] out=FULL` verified the layout.
6. `cursor_to_cell(grid="2x2", cell="out")`, `gui_click()` consumed the ingredients and produced `craft_item torch +4`; `cursor_to_slot(slot=2)`, `gui_click()` stowed all four torches.
7. The cursor tracker continued reporting the consumed charcoal and stick after the authoritative 2x2 grid became empty. Normal close was refused; after confirming the craft event, empty grid, and torch inventory, `close_inventory(force=true)` is the safe way to clear this stale warning.

Current-run confirmation: the same geometry with coal produced `craft_item torch +4` at step 3323. Banking one spare coal and three spare sticks before taking output left coal x1, sticks x3, and torches x4; placement at 3338 left torches x3.
