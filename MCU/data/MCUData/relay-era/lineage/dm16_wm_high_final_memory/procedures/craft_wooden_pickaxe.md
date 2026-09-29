# wooden_pickaxe
Preconditions: 3 spruce planks and 2 sticks safely inventoried; crafting-table 3x3 screen open; cursor empty.

1. Lift the plank stack from its known inventory slot with `cursor_to_slot` then `gui_click`.
2. For cells 0, 1, and 2, call `cursor_to_cell(grid="3x3", cell=<cell>)` then `gui_right_click()` to fill the top row one plank at a time.
3. Return any remaining planks to their inventory slot with `cursor_to_slot` then `gui_click` before handling sticks.
4. Lift the stick stack from its known inventory slot with `cursor_to_slot` then `gui_click`.
5. Put one stick in cell 4 and one in cell 7 using `cursor_to_cell` followed by `gui_right_click()` for each.
6. Return the remaining sticks to their inventory slot; verify the 3x3 row reports `out=FULL`.
7. Call `cursor_to_cell(grid="3x3", cell="out")`, then `gui_click()` to take the pickaxe. This cleared the recipe and produced `craft_item wooden_pickaxe +1` plus the milestone at live step 1030.
8. Re-land with `cursor_to_slot(slot=0)` and `gui_click()` in a short guarded segment. At live step 1035, `[INV] wooden_pickaxe +1` proved the tool was banked.

Live-run caveat: after the 3x3 recipe cleared, the runner's off-inventory summary still listed planks/sticks solely because unopened 2x2/furnace geometry rows were noisy. The actual open 3x3 row was empty and STATE already listed the ingredients in inventory; in this exact state a forced close is lossless.
8. Move to a known empty hotbar slot and click to stow the pickaxe before closing the screen.

Observed detail: the off-inventory text can include stale ingredient names, while the frame visibly shows the crafted pickaxe attached to the pointer. Trust the craft event for recipe success, but still require an inventory delta/state before closing.
