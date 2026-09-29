# mechanism_place_block_helper_gui_guard

- kind: mechanism
- status: confirmed
- confidence: 0.99
- created_step: 4877
- updated_step: 4895
- depends_on: goal_furnace

## Statement

The place_block helper is misrouted through GUI clicking; raw use reliably places a held block when aimed at an exposed supporting face with a free adjacent destination cell.

## Evidence

- At steps 4875-4876 place_block produced two consecutive 'gui_right_click: screen is closed' notes. Earlier raw-use placements of crafting tables at steps 1103, 2578 and 3720 each caused an immediate inventory decrement. The step-4877 raw use on the very close target did not decrement furnace, so target validity remains part of this test.
- At steps 4877 and 4879 raw use against very near/side-face targets produced no inventory decrement or use_item event. Earlier verified cobblestone placement succeeded at step 2527 only after backing away and aiming at a face with clearance.
- At step 4895 raw use produced [INV] furnace -1 after backing away and targeting the exposed top face near (-3006.5,68.95,-5569.5), confirming successful placement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
