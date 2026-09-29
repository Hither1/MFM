# resource_stone_pickaxe_secure

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 4800
- depends_on: goal_stone_pickaxe, state_death_and_dropped_kit_6248

## Statement

The selected stone pickaxe remains secure in zero-based hotbar slot 3 at step 4800 with about 101 of 131 uses remaining.

## Evidence

- events/events.jsonl contains 29 use_item stone_pickaxe records after craft step 3390 and zero break_item records; frame 4200 shows it selected.
- events/events.jsonl contains exactly 50 current-prefix stone-pick uses and no break event; frame 4800 shows the pick selected.
- Current events contain exactly 71 stone-pick uses and no break; frame 5400 shows the selected physical pick.
- events contains 98 current-prefix use_item stone_pickaxe records and no break_item record; frame 8000 visibly shows it selected.
- Current events contain 103 use_item stone_pickaxe records and no break_item record; frame 8600 visibly shows the pick selected.
- craft_item/milestone fired at event lines 102-103 step 3427; INV stone_pickaxe +1 fired at 3432; no later stone-pick use or break event exists and frame 3600 shows it.
- Craft/milestone fired at 3427 and INV +1 at 3432. Current events contain exactly 17 stone-pick use events and no break_item; frame 4200 visibly shows the selected physical pick.
- Current events contain exactly 30 use_item stone_pickaxe records and no break_item event; frame 4800 shows it selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
