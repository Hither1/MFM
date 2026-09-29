# furnace
Preconditions: 8 cobblestone in inventory; 3x3 crafting-table screen open.
1. Lift the cobblestone stack with `cursor_to_slot` + `gui_click`.
2. Place one cobblestone with `gui_right_click` into cells 0, 1, 2, 3, 5, 6, 7, and 8.
3. Return any remainder to its inventory slot before taking the output.
4. `cursor_to_cell(grid="3x3", cell="out")`, then `gui_click()` crafts the furnace; verify `craft_item furnace`.
5. The accumulated off-inventory label may still say cobblestone after the output click. The craft event plus the cleared 3x3 grid are authoritative: immediately land on a known empty inventory slot and click to stow the furnace.

Verified at step 3802. The ring consumed eight cobblestone and the environment confirmed the furnace milestone.
