# torch
Preconditions: inventory screen open; at least 1 coal and 1 stick; empty slot for output.
1. Lift the coal stack from its inventory slot with `cursor_to_slot` + `gui_click`.
2. Land on 2x2 cell 0 and `gui_right_click()` once.
3. Return the remaining coal to its source slot before continuing.
4. Lift the stick stack, land on 2x2 cell 2, and `gui_right_click()` once.
5. Return the remaining sticks to their source slot. Confirm the relevant 2x2 row reports cells `[0,2] out=FULL`.
6. Land on the 2x2 output and `gui_click()`. A successful click emits `craft_item torch +4`; if the first click produces no event, re-land on the output and click again.
7. Bank the four torches into an empty inventory/hotbar slot. After crafting, the 2x2 grid is empty even if the aggregate `off-inventory` label still lists the consumed coal and stick.

Verified at steps 5711-5753: one of two coal was preserved, three of four sticks were preserved, and four torches were banked in hotbar slot 7 (the eighth hotbar position).
