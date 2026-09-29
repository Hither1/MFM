# replacement wooden pickaxe

Preconditions: crafting-table screen open; at least 3 planks and 2 sticks in inventory.

1. Lift the plank stack with `cursor_to_slot` + `gui_click`.
2. Place one plank in 3x3 cells 0, 1, and 2 using `cursor_to_cell` + `gui_right_click`.
3. Return any spare planks to their inventory slot before lifting sticks.
4. Lift sticks and place one in cells 4 and 7; return any remainder to inventory.
5. Move to 3x3 `out`, click the wooden pickaxe, then move to an empty hotbar slot and click to stow it.

Verified at step 6994 (`craft_item wooden_pickaxe`) and step 6998 (`[INV] wooden_pickaxe +1`). Ignore occupied rows for unopened grid geometries; only the open 3x3 row is authoritative.
