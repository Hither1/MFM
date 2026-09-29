# resource_rebuild_stone_pick_7259

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 7356
- updated_step: 11600
- depends_on: goal_stone_pickaxe, resource_dropped_planks_sticks_7127, state_death_and_dropped_kit_6248, location_current_crafting_table, resource_current_cobblestone

## Statement

The replacement stone pickaxe used during the late tunnel search is exhausted and broke at step 11319.

## Evidence

- Steps 7340-7350 verify table mining and pickup; authoritative step-7707 inventory contains the table, x3 planks, x2 sticks, wooden pickaxe with 46 uses, and x1 cobblestone. The yaw -120 stair descended 0 blocks and mine_forward stalled, so the diagonal surface route is refuted as an efficient descent.
- Events verify cobblestone pickups at 7627, 7748, and 7777; frame 7800 hotbar shows cobblestone x3, sticks x2, table, and wooden pickaxe.
- Authoritative step-7956 inventory lists crafting_table x1, cobblestone x9, stick x2, and wooden_pickaxe x1 (38/59 uses). Events at steps 7941 and 7951 verify the additional stone breaks and cobblestone pickups during the direct descent to y55.
- Step 8094 authoritative inventory lists cobblestone x12, stick x2, and wooden_pickaxe x1; GUI open=True. The guard note says the cursor was 69px from the prior landing when the separated click ran and explicitly directs re-landing before clicking.
- events/events.jsonl records craft_item stone_pickaxe +1 at step 8149; logs step 8153 records [INV] stone_pickaxe +1 and current state places it in hotbar slot 4.
- Craft/stow verified at 8149/8153; exactly 34 use_item stone_pickaxe events occur from 8149 through 9000 and no break_item event exists.
- Craft verified at 8149; exactly 84 authoritative use_item stone_pickaxe events through 10185 leave 47 uses.
- break_item stone_pickaxe fired at 11319 and the later inventory/GUI state contains no pickaxe.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
