# state_cursor_wooden_pickaxe_4458

- kind: state
- status: stale
- confidence: 0.99
- created_step: 4458
- updated_step: 7800
- depends_on: goal_wooden_pickaxe, location_furnace_worksite_4390

## Statement

The wooden pickaxe formerly stored in the furnace fuel slot has now been consumed as fuel for the first iron smelt; it is not recoverable inventory.

## Evidence

- Step 4409 records wooden_pickaxe -1 when lifted from hotbar slot 0; steps 4412-4458 continuously report wooden_pickaxex1 off-inventory, and no later inventory addition or furnace transfer is recorded.
- The attached step-4509 frame visibly shows the wooden-pickaxe icon inside the furnace fuel slot while the measured cursor is outside the container; [GRID] also reports furnace [fuel].
- At 7759 the furnace showed fuel; by 7781 GRID showed only furnace input while flames remain active in frame 7800, the normal transition when a fuel item is consumed into burn time.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
