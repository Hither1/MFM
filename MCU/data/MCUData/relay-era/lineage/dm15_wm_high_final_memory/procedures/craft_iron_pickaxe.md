# craft_iron_pickaxe
Preconditions: 3 iron ingots and at least 2 sticks in inventory; 3x3 crafting-table screen open; cursor empty.

1. Lift the iron-ingot stack from its known inventory slot with `cursor_to_slot`, then `gui_click`.
2. Put one ingot in each of cells 0, 1, and 2 with `cursor_to_cell(grid="3x3", cell=N)` followed by `gui_right_click()`.
3. Lift the stick stack, then put one stick in cell 4 and one in cell 7 with the same closed-loop cell landing and right-click sequence.
4. Return any spare stick to its inventory slot before collecting the output. The authoritative 3x3 row then reports `out=FULL`.
5. Land on `cursor_to_cell(grid="3x3", cell="out")` and `gui_click()`. In the live run this produced both `craft_item iron_pickaxe +1` and the verified milestone at step 8008.
6. Stow the pickaxe in a known empty hotbar slot before closing the screen.

Observed quirk: after the pickaxe was stowed (`[INV] iron_pickaxe +1` at step 8013), the cursor tracker continued reporting all three consumed ingots and two consumed sticks although the authoritative 3x3 row was empty. As with the confirmed stone-pick and torch crafts, `close_inventory(force=true)` is lossless in this exact stale-tracker state; trust the empty real grid, craft event, and inventory delta.
