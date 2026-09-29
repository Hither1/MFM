# state_inventory_4179

- kind: state
- status: stale
- confidence: 1.00
- created_step: 4200
- updated_step: 4800
- depends_on: goal_stone_pickaxe

## Statement

The step-4179 inventory snapshot has been superseded by furnace crafting and later mining; it must not guide current slot assumptions.

## Evidence

- Ground-truth craft_item stone_pickaxe fired at 4166; [INV] stone_pickaxe +1 at 4170, wooden_pickaxe -1 at 4176, and the current frame visibly shows stone pickaxe, cobblestone x9, sticks x4.
- Furnace crafted at 4279; step-4800 hotbar and later pickup events show a different inventory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
