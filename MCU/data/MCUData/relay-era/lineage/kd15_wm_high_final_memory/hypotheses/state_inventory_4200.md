# state_inventory_4200

- kind: state
- status: stale
- confidence: 1.00
- created_step: 4200
- updated_step: 4800
- depends_on: goal_stone_pickaxe, goal_mine_cobblestone, mechanism_dirt_pillar_return_2325

## Statement

The step-4200 inventory snapshot is historical and superseded by mining and descent; use state_inventory_4800 for live planning.

## Evidence

- Step-4200 hotbar frame plus current-run event accounting from step 3600; no wood, coal, or iron event occurred.
- Twenty additional stone-pick uses and multiple dirt/cobblestone pickups occurred after step 4200.
- Current frame shows the five stacks; event accounting gives 16 cobble pickups minus four placements = 12, and no later inventory event changed them.
- Attached step_4200.png gives exact visible stacks; current events reconcile dirt 12 pickup minus 7 use=5, cobble 20 pickup minus 6 placement minus 3 recipe=11, and decorative stacks exactly.
- Current events add 26 stone-pick uses and many pickups after step 4200, and the final visited row is step 4800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
