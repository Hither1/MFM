# planks

Preconditions: survival inventory open; log stack in a player slot; empty slot available.

1. `cursor_to_slot(slot=LOG_SLOT)`, `gui_click()` lifts the log; require `[INV] spruce_log -N`.
2. `cursor_to_cell(grid="2x2",cell=0)`, `gui_right_click()` places one log. Confirm survival-grid cell 0 occupied and `out=FULL`.
3. `cursor_to_cell(grid="2x2",cell="out")`, `gui_click()` takes four planks; require `craft_item spruce_planks +4` (current-reset proof: step 1391).
4. `cursor_to_slot(slot=EMPTY_OR_PLANK_SLOT)`, `gui_click()` banks output; require `[INV] spruce_planks +4` (current-reset proof: step 1396).
5. If another log remains off-inventory/in cell 0, repeat output extraction or retrieve and place it deliberately. Stow all residual cursor/grid stacks before closing.

Failure hazard: the cursor item label remained stale during the verified current-reset craft. Use events, `[INV]`, and the open screen's 2x2 `[GRID]` row to advance, but still obey the close guard.
