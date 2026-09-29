# resource_free_slot_for_cobble_2543

- kind: resource
- status: stale
- confidence: 0.95
- created_step: 2543
- updated_step: 4200
- depends_on: state_stone_below_pit_2443, resource_reserve_wood, goal_stone_pickaxe

## Statement

The earlier cobblestone-capacity workaround is historical; after banking the stone pickaxe and intentionally dropping the obsolete wooden pickaxe, inventory capacity is no longer the active blocker.

## Evidence

- At step 2897 a pitch-45 wall use did not consume dirt, and the step-2993 enlarged item sprite is visibly dirt rather than cobblestone. The player stands on stone at y62 in a tight pocket, so looking straight down and jump-placing targets the temporarily vacated cell above the stone floor.
- Step 2993 shows dirt x1 in hand; step 3000 shows an empty selected slot and empty hand while maps records a jump from y62 to y63.25. events has not yet recorded use_item dirt, so this remains visually supported rather than event-confirmed.
- events records use_item dirt at step 3004; at step 3050 [INV] records stick -6 and [CURSOR] reports stick x6, while the wooden pickaxe remains banked.
- At step 3053 the inventory force-closed with stick x6 on the cursor, creating a stick item entity near (-3001.7,63,-5560.3); current state lists only wooden_pickaxe in inventory.
- Step 3208 records pickup stick +6 and current inventory is dirt x1, sticks x6, wooden pickaxe x1. The same look-down jump-place sequence consumed dirt at step 3004, so repeating it should free the dirt stack slot.
- events records use_item dirt at step 3220 and the current inventory no longer lists dirt, but step 3282 still reports zero free slots with sticks and wooden pickaxe present. The prior force-close at step 3053 successfully removed sticks from inventory.
- [INV] cobblestone +3 at step 3327 and stick +6 at step 3335; current inventory lists dirt, cobblestone, sticks, and wooden pickaxe with zero free slots.
- At step 4170 [INV] records stone_pickaxe +1; at 4176 wooden_pickaxe -1 and the forced close at 4179 drops it. Step-4200 hotbar shows one free compact slot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
