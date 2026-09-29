# wooden_pickaxe
Preconditions: crafting-table screen open; at least 3 planks and 2 sticks banked.

1. Lift planks from their inventory slot and right-click once into 3x3 cells 0, 1, and 2.
2. Return to the source inventory slot and left-click to bank the plank remainder.
3. Lift sticks and right-click once into cells 4 and 7.
4. Return to the source inventory slot and left-click to bank the stick remainder.
5. Confirm the table row reports `out=FULL`, then `cursor_to_cell(grid="3x3", cell="out")` and `gui_click()`.
6. The first output click at step 1954 did not register even though the pointer was aligned; re-landing on output and clicking again fired `craft_item wooden_pickaxe +1` at step 1956.
7. Bank the cursor-held pickaxe in an empty player slot before closing.

Current-reset confirmation: the output extraction at step 2148 fired both the `craft_item wooden_pickaxe +1` statistic and milestone, left the 3x3 grid empty, and put the crafted pickaxe on the GUI cursor over zero-based hotbar slot 0. Pair `cursor_to_slot(slot=0)` with `gui_click()` before a guarded close.

Failure seen: ingredient placement can visually appear one action ahead in `[GRID]`; only `[INV]` changes and the craft event prove clicks succeeded.
