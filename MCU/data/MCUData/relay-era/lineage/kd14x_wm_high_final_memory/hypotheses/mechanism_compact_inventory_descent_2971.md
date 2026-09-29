# mechanism_compact_inventory_descent_2971

- kind: mechanism
- status: stale
- confidence: 0.99
- created_step: 2971
- updated_step: 3600
- depends_on: goal_wooden_pickaxe, goal_crafting_table, goal_mine_cobblestone

## Statement

The earlier inventory-capacity blockade is resolved: consuming the three-dirt stack created a cobblestone slot, and later cobblestone pickups merge into it even with all five slots occupied.

## Evidence

- Step 2971 inventory has exactly wooden_pickaxe, spruce_planks x3, and stick x2 with zero free slots; the crafting-table GUI is open at the current pose with an empty relevant 3x3 grid. Placing the plank stack frees one slot for the table, and tool breakage later frees the cobblestone slot.
- Steps 2909 and 2980-2984 show use/place attempts with no spruce_planks inventory decrement; step 3000 still shows planks x3, sticks x2, and wooden pickaxe occupying all slots.
- use_item dirt fired three times through step 3126; cobblestone pickups then accumulated to x9 through step 3573 without wooden-pick breakage.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
