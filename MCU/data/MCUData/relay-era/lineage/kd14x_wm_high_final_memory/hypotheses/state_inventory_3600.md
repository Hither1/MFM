# state_inventory_3600

- kind: state
- status: stale
- confidence: 1.00
- created_step: 3600
- updated_step: 4200
- depends_on: goal_furnace, goal_stone_pickaxe

## Statement

The step-3600 inventory snapshot is historical and superseded by the y49 descent and east-tunnel mining through step 4200.

## Evidence

- Step-3600 frame shows the three held stacks and empty remaining hotbar; event accounting gives 15 stone-pick uses and 27 wooden-pick uses, and no resource events add wood/fuel/iron after the furnace craft.
- Events after step 3600 record two wooden-pick uses, fourteen stone-pick uses, eight visible cobblestone total, and a changed dirt stack.
- Step-3600 state/frame plus event accounting: 19 wooden-pick uses and nine cobblestone pickups; no coal, ore, furnace, or iron events.
- step_3600.png visibly shows these exact three stacks; events record craft_item stone_pickaxe at 3377 and only grass/dirt uses afterward; current-reset visited row 3600 gives the pose.
- Current-reset events after step 3600 add dirt x5 net, cobblestone x9 net, diorite x3, andesite x4, granite x4; the attached step-4200 frame confirms the new hotbar.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
