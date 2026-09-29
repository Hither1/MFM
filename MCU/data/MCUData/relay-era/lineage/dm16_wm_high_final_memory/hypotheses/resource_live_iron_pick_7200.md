# resource_live_iron_pick_7200

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 7200
- updated_step: 10800
- depends_on: goal_iron_pickaxe, location_current_deep_column_target_6330

## Statement

The selected iron pickaxe has exactly 64 of 250 uses remaining at step 10800; the 14.9-cell route and one diamond extraction are durability-feasible at both recent west-mining rates.

## Evidence

- The live STATE reports Held: iron_pickaxe (216/250 uses left).
- The pick was crafted at step 6330; exactly 54 subsequent use_item iron_pickaxe events and no break_item event exist through 7800.
- The pick was crafted at step 6330; events contain exactly 83 later use_item iron_pickaxe records and no break_item iron_pickaxe through step 8400.
- The pick was crafted at event step 6330; exactly 111 later use_item iron_pickaxe events and no break_item iron_pickaxe event exist through step 9000.
- The pick was crafted at 6330; exactly 135 later use_item iron_pickaxe events and no break event occur through step 9600.
- STATE explicitly reports Held: iron_pickaxe (109/250 uses left); six verified iron-pick uses occurred after the 115-use step-9600 checkpoint and no break event occurred.
- The pick was crafted at event step 6330; exactly 159 later use_item iron_pickaxe events and no break_item event exist through 10200, including the downward stone break at 10197.
- The pick was crafted at 6330; exactly 186 later use_item iron_pickaxe events and zero break_item events exist through 10800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
