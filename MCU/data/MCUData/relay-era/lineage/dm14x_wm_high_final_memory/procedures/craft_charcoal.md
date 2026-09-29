# craft_charcoal
Preconditions: one log, one plank, placed furnace, player adjacent, non-placeable item selected.
1. Aim at furnace and `use_until_gui`.
2. Lift the log from its inventory slot, land on `cursor_to_cell(grid="furnace", cell=0)`, and `gui_click()` to deposit it.
3. Lift the plank, land on `cursor_to_cell(grid="furnace", cell=1)`, and `gui_click()` to fuel it.
4. Wait 200 ticks. Land on `cursor_to_cell(grid="furnace", cell="out")`, `gui_click()` to take output, then stow it in an empty slot.
Evidence: input/fuel were present at step 5016; `craft_item charcoal +1` fired at step 5224 and `[INV] charcoal +1` followed.
Quirk: the cursor tracker continued listing the consumed log/plank. Trust furnace GRID, inventory deltas, and the craft event.
