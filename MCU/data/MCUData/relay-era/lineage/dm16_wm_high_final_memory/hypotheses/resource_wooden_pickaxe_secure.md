# resource_wooden_pickaxe_secure

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 1175
- updated_step: 3000
- depends_on: goal_wooden_pickaxe

## Statement

The wooden pickaxe remains selected in hotbar slot 0 at step 3000 with about 34 of 59 uses left.

## Evidence

- The step-1885 craft event and cleared active 3x3 grid prove creation, while no [INV] wooden_pickaxe +1 has yet recorded the pending final gui_click.
- At step 1890 [INV] wooden_pickaxe +1 fired after the cursor was landed on hotbar slot 2, and authoritative STATE at step 2075 lists hotbar.3=wooden_pickaxe x1.
- INV wooden_pickaxe +1 fired at 1890; frame 2400 visibly shows it selected; events record exactly seven use_item wooden_pickaxe increments at 2215, 2241, 2276, 2299, 2333, 2359, and 2395 with no break_item event.
- events/events.jsonl contains 21 use_item wooden_pickaxe increments and no break_item wooden_pickaxe; frame 3000 shows the selected pick.
- events/events.jsonl records craft_item wooden_pickaxe and the milestone at step 1323; frame step_1323 shows the pickaxe attached to the pointer, while the prior deposit click aborted because the pointer had moved since its servo landing.
- events/events.jsonl verifies craft_item wooden_pickaxe and its milestone at step 1323; logs record [INV] wooden_pickaxe +1 at step 1328; authoritative step-1494 STATE lists hotbar.1=wooden_pickaxe x1 and the active 3x3 GRID is empty.
- events contain 22 wooden-pick use increments and no break_item; frame 2400 shows the selected pick and partial durability bar.
- Events record 25 use_item wooden_pickaxe increments and no break_item; enlarged frame 3000 shows the selected tool and durability bar.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
