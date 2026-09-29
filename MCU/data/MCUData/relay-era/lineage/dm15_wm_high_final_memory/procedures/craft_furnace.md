# craft_furnace
Preconditions: at least 8 cobblestone in inventory; adjacent 3x3 table screen open; cursor empty.
1. `cursor_to_slot(slot=4)`, `gui_click()` lifted cobblestone x48 (`INV -48` at 5930).
2. For cells `0,1,2,3,5,6,7,8`, pair `cursor_to_cell(grid="3x3",cell=N)` with `gui_right_click()`.
3. `cursor_to_slot(slot=4)`, `gui_click()` returned x40 before output collection; active GRID reported the ring and `out=FULL`.
4. `cursor_to_cell(grid="3x3",cell="out")`, `gui_click()` cleared the active grid; `craft_item furnace` and milestone fired at 5997.
5. CURSOR continued to say cobblestone x8 although those were consumed. Trust empty active GRID plus craft event, then in the same plan land on a genuinely empty slot and click; require `INV furnace +1` before closing.

Failure observed: cursor position can recenter across plan boundaries, causing a later click to abort 67–134 px from the prior landing. Always pair landing and click in one plan.
