# resource_stone_pickaxe_secure

- kind: resource
- status: active
- confidence: 1.00
- created_step: 3000
- updated_step: 7800
- depends_on: goal_stone_pickaxe, state_death_and_dropped_kit_6248

## Statement

The stone pickaxe is selected in zero-based hotbar slot 5 with 37/131 uses remaining at step 7800.

## Evidence

- Current events verify craft at 2194, logs verify [INV] stone_pickaxe +1 at 2199, no use/break_item stone_pickaxe follows through 2400, and frame 2400 shows it in slot 5; the prior step-11319 claim was future-trajectory contamination.
- Craft and deposit verified at 2194/2199; events contain 14 use_item stone_pickaxe and no break_item through step 3000.
- There are 23 current-run use_item stone_pickaxe events after its craft at 2194 and no break_item event; frame 3600 shows it selected.
- There are 47 current-run use_item stone_pickaxe events after craft at 2194 and no break_item event through 4200; frame 4200 shows it selected.
- events contain 68 use_item stone_pickaxe events after craft and no break_item event; frame 4800 shows it selected.
- Exactly 68 current stone-pick uses and no break event exist; frame 5400 shows the pick in slot 5.
- It was crafted at 2194; exactly 85 current-prefix use_item stone_pickaxe events and no break_item event exist through 7200.
- Exactly 94 current-prefix use_item stone_pickaxe events and no break_item event exist after its step-2194 craft; frame 7800 shows it selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
