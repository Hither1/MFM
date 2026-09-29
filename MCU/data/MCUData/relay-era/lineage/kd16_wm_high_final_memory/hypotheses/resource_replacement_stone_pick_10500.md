# resource_replacement_stone_pick_10500

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 10500
- updated_step: 11384
- depends_on: goal_stone_pickaxe, goal_mine_iron_ore

## Statement

A replacement stone pickaxe was crafted at step 11375 and banked in hotbar slot 0; it is now available for the final iron search.

## Evidence

- Authoritative step-10500 inventory contains cobblestone x57 and sticks x3; procedures/stone_pickaxe.md records the verified 3-cobble, 2-stick sequence.
- Step-10800 hotbar visibly shows cobblestone x57 and sticks x3; the stone-pick recipe was verified at step 4166.
- Step 10850 authoritative state reports cobblestone x57, sticks x3, stone pickaxe 2/131, and 0 slots free. Two overhead dirt blocks are directly reachable in the trench, so using the final two durability points also clears the pillar route.
- At step 10994 inventory has zero free slots, one nearly exhausted stone pick, cobblestone x55, and sticks x3; the frame crosshair lies on a nearby stone face.
- At step 11074 mine_ahead broke and picked up one dirt while the prior authoritative state showed the stone pick at 2/131 uses. The new frame centers a reachable stone face; cobblestone can merge into its existing stack, leaving the broken-pick slot free.
- events.jsonl records break_item stone_pickaxe at step 11110; the current state shows no pick in inventory, cobblestone x56, sticks x3, and hotbar.1 empty.
- events/events.jsonl records craft_item stone_pickaxe +1 at step 11375, and the step-11384 inventory lists stone_pickaxe x1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
