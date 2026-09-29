# resource_wooden_pickaxe_secure

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 1175
- updated_step: 3000
- depends_on: goal_wooden_pickaxe

## Statement

The selected wooden pickaxe remains physically owned at live step 3000 with about 38 of 59 uses left after 21 verified use_item increments and no break_item event.

## Evidence

- The step-781 craft event proves creation, the active recipe grid cleared, and the frame visibly shows the pickaxe at the cursor over empty hotbar slot 1; this turn tests the deposit via an inventory delta.
- Authoritative STATE at step 1016 lists wooden_pickaxe x1, Held wooden_pickaxe (55/59 uses left), and the GUI is closed.
- Held state reported 55/59 at step 1016; seven later stone-use events occurred through 1194 with no break_item event; frame 1200 shows the selected tool.
- Step 1649 reported 36 uses; one later stone break occurred at 1699 and no break_item event exists. Frame 1800 shows the tool.
- The step-1885 craft event and cleared active 3x3 grid prove creation, while no [INV] wooden_pickaxe +1 has yet recorded the pending final gui_click.
- At step 1890 [INV] wooden_pickaxe +1 fired after the cursor was landed on hotbar slot 2, and authoritative STATE at step 2075 lists hotbar.3=wooden_pickaxe x1.
- INV wooden_pickaxe +1 fired at 1890; frame 2400 visibly shows it selected; events record exactly seven use_item wooden_pickaxe increments at 2215, 2241, 2276, 2299, 2333, 2359, and 2395 with no break_item event.
- events/events.jsonl contains 21 use_item wooden_pickaxe increments and no break_item wooden_pickaxe; frame 3000 shows the selected pick.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
