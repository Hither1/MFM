# crafting_table
Preconditions: survival inventory open; four planks in a known slot; real cursor empty.
1. `cursor_to_slot(plank_slot)`, `gui_click()`; require the plank inventory decrement.
2. For 2x2 cells 0,1,2,3: land with `cursor_to_cell`, then `gui_right_click()` once.
3. Require active `[GRID] 2x2 cells [0,1,2,3] out=FULL`.
4. Land on 2x2 output and `gui_click()`. Current-run ground truth fired `craft_item crafting_table +1` and the milestone at step 591.
5. Land on a known empty hotbar slot and `gui_click()`; `[INV] crafting_table +1` at step 595 proved it was banked.

Observed quirk: cursor text continued to report a consumed spruce log although the active grid was empty and the frame showed two logs plus the table banked. Trust active GRID, inventory deltas, events, and visible stacks; do not recover the phantom label.
