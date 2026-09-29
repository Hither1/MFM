# resource_free_slot_for_cobble_2543

- kind: resource
- status: active
- confidence: 0.98
- created_step: 2543
- updated_step: 3762
- depends_on: state_stone_below_pit_2443, resource_reserve_wood, goal_stone_pickaxe, goal_wooden_pickaxe, goal_mine_cobblestone

## Statement

The cobblestone pickup-capacity blocker has recurred: six dirt pickups filled the only spare compact slot while three verified stone breaks left cobblestone drops uncollected below the live shaft. Force-drop the dirt at y60 and move down/away before sweeping the fresh drops.

## Evidence

- [INV] cobblestone +3 at step 3327 and stick +6 at step 3335; current inventory lists dirt, cobblestone, sticks, and wooden pickaxe with zero free slots.
- At step 4170 [INV] records stone_pickaxe +1; at 4176 wooden_pickaxe -1 and the forced close at 4179 drops it. Step-4200 hotbar shows one free compact slot.
- Step 2241 authoritatively reports zero free slots, wooden pickaxe in hotbar.1, and sticks x2 in hotbar.2 at (-3000.8,66,-5564.7). Earlier verified force-closes removed cursor-held stacks from inventory, including sticks, so the same mechanism is appropriate before moving down away from the drop.
- Steps 2250-2253 removed stick x2 from inventory and force-closed them onto the ground; step 2277 then verified mine_block grass_block while the live state lists only wooden_pickaxe.
- Three planks were consumed by use events at 2218/2224/2235; stick x2 left inventory at 2250 and was dropped at 2253; frame 2400 shows only the wooden pickaxe in the hotbar.
- Step 3245 reports zero free slots, wooden pickaxe in hotbar.1 and sand x2 in hotbar.2. Steps 2250-2253 previously removed sticks with the same cursor-lift plus force-close sequence.
- Dirt left inventory at step 3383 and was force-dropped at 3386; sand left at 3423 and was force-dropped at 3426. Travel moved beyond both caches and no subsequent pickup event exists.
- Current step 3762 reports zero free slots with wooden_pickaxe and dirt x6. Events verify stone breaks at 3668, 3697, and 3726 but no cobblestone pickup; the frame visibly shows a drop below.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
