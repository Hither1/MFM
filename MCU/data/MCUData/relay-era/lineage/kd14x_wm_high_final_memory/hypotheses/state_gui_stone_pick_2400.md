# state_gui_stone_pick_2400

- kind: state
- status: stale
- confidence: 1.00
- created_step: 2400
- updated_step: 3000
- depends_on: goal_stone_pickaxe, mechanism_table_aim_2349

## Statement

The partial stone-pick crafting GUI state at step 2400 is historical; the recipe completed at 2438 and the GUI is now closed.

## Evidence

- Steps 2390-2399 verify cobblestone -6, cursor landing/click on cell 0, and cursor landing on cell 1; zoomed step_2400.png visibly shows cell 0 occupied and the carried cobble icon over cell 1.
- events records the stone-pick craft at 2438; subsequent mining and the step-3000 frame supersede the partial grid state.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
