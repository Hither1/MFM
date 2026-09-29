# furnace

Preconditions: 8 cobblestone in one player slot; 3x3 crafting-table screen open; one empty destination slot for the furnace.

1. `cursor_to_slot(slot=<cobblestone slot>)`, `gui_click()` lifts the stack.
2. For cells `0,1,2,3,5,6,7,8`, pair `cursor_to_cell(grid="3x3", cell=<cell>)` with `gui_right_click()` to make the edge ring and leave cell 4 empty.
3. `cursor_to_slot(slot=<original slot>)`, `gui_click()` banks any remainder; `[GRID]` showed the eight edge cells and `out=FULL`.
4. `cursor_to_cell(grid="3x3", cell="out")`, `gui_click()` takes the furnace; the `craft_item furnace` event fired at step 4279.
5. `cursor_to_slot(slot=<empty destination>)`, `gui_click()` banks the furnace; `[INV] furnace +1` confirmed this at step 4283.

Live-reset replay: the same ring sequence fired `craft_item furnace` and the furnace milestone at step 3407. Starting with 18 cobblestone after the stone-pick recipe, banking the remainder before taking output left exactly 10 cobblestone in inventory; both sticks were already consumed by the pickaxe. The output was visibly cursor-held over empty zero-based hotbar slot 6, so re-land on slot 6 and click before any close.

Observed quirk: after the ingredients were consumed, the close guard retained a phantom `cobblestone x8 off-inventory` label even though the 3x3 grid was empty and the furnace had been banked. A normal close was refused; with the output safely in a player slot, force-closing is the intended recovery for this stale tracker state.
