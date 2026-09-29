# resource_stone_pickaxe_secure

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 8600
- depends_on: goal_stone_pickaxe, state_death_and_dropped_kit_6248

## Statement

The selected live stone pickaxe has 28 of 131 uses left at step 8600; reserve it for ascent access until the iron pick is banked.

## Evidence

- The step-3390 output click fired craft_item stone_pickaxe and the next cursor servo landed at hotbar slot 0; the planned click directly tests secure deposit.
- At step 3395, [INV] reports stone_pickaxe +1 and authoritative STATE lists stone_pickaxe x1 in hotbar slot 1 after the step-3390 craft event.
- [INV] stone_pickaxe +1 fired at 3395; events record uses at 3561, 3582, and 3600 with no break_item, and frame 3600 visibly shows it selected.
- events/events.jsonl contains 29 use_item stone_pickaxe records after craft step 3390 and zero break_item records; frame 4200 shows it selected.
- events/events.jsonl contains exactly 50 current-prefix stone-pick uses and no break event; frame 4800 shows the pick selected.
- Current events contain exactly 71 stone-pick uses and no break; frame 5400 shows the selected physical pick.
- events contains 98 current-prefix use_item stone_pickaxe records and no break_item record; frame 8000 visibly shows it selected.
- Current events contain 103 use_item stone_pickaxe records and no break_item record; frame 8600 visibly shows the pick selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
