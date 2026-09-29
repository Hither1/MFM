# craft_spruce_planks

Preconditions: inventory screen open; spruce logs in a known player slot; at least one empty player slot available for the remainder.

1. `cursor_to_slot(slot=0)`, then `gui_click()` lifted the four-log stack.
2. `cursor_to_cell(grid="2x2", cell=0)`, then `gui_right_click()` placed one log in the grid. The cursor readout did not immediately decrease, so subsequent inventory/event evidence was used for verification.
3. `cursor_to_slot(slot=0)`, then `gui_click()` returned the remaining three logs to slot 0; `[GRID] 2x2 ... out=FULL` proved the plank recipe.
4. `cursor_to_cell(grid="2x2", cell="out")`, then `gui_click()` while one log remained on the cursor did not visibly collect output immediately. A later slot click produced `craft_item spruce_planks +4` at step 742 and left four planks in slot 0 with all four logs on the cursor.

Failure seen: do not try to collect recipe output while the cursor still holds an incompatible item. Stow all remaining logs in a different empty slot first, then collect output with an empty cursor.
