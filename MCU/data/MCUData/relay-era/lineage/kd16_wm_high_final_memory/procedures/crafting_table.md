# crafting_table

Preconditions: survival inventory open; at least four planks in a player slot; empty player slot available for the output.

1. `cursor_to_slot(slot=0)`, `gui_click()` lifted the spruce-plank stack from hotbar slot 0; `[INV] spruce_planks -8` verified the lift.
2. For each 2x2 crafting cell 0, 1, 2, and 3: `cursor_to_cell(grid="2x2", cell=N)`, then `gui_right_click()` placed one plank.
3. `cursor_to_slot(slot=0)`, `gui_click()` banked the four-plank remainder before touching the output; `[INV] spruce_planks +4` verified it.
4. `[GRID]` for the survival 2x2 screen showed cells `[0,1,2,3] out=FULL`.
5. `cursor_to_cell(grid="2x2", cell="out")`, `gui_click()` took the output; `craft_item crafting_table +1` and the milestone fired at step 1151.
6. Re-land on an empty inventory slot and `gui_click()` to bank the table before closing.

Observed quirk: `[CURSOR]`'s off-inventory item label remained stale as `spruce_logx2` during this sequence. Trust `[INV]`, `[GRID]`, the visible output consumption, and `events.jsonl`. The first `cursor_to_slot(slot=1)` stopped between slots, so repeat the closed-loop landing before clicking.
