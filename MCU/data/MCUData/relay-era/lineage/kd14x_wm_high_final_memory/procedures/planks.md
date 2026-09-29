# planks
Preconditions: survival inventory screen open; at least one log in a player inventory slot; one empty destination slot.

1. `cursor_to_slot(slot=<log slot>)`, `gui_click()` lifts the log; require `[INV] spruce_log -1`.
2. `cursor_to_cell(grid="2x2", cell=0)`, `gui_right_click()` places one log; require 2x2 `out=FULL`.
3. `cursor_to_cell(grid="2x2", cell="out")`, `gui_click()` takes four planks; require `craft_item spruce_planks +4`.
4. `cursor_to_slot(slot=<empty or original slot>)`, `gui_click()` banks the output; require `[INV] spruce_planks +4` before closing.

Current-run evidence: log pickup at 6974, output event at 6998, and inventory gain at 7002. The cursor label continued to name the consumed log; the event, emptied relevant grid, and inventory delta overrode it.
