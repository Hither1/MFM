# resource_iron_slot_dirt_10155

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 10155
- updated_step: 10200
- depends_on: goal_mine_iron_ore

## Statement

Dirt x3 was deliberately removed at step 10167, leaving ample inventory capacity for ore and ingots.

## Evidence

- Step 10155 reports zero slots free and dirt x3 in hotbar slot 5; confirmed forced-close behavior removes a cursor-held stack.
- gui_click produced dirt -3 at 10164 and force-close reported the cursor stack dropped at 10167; step-10200 hotbar visibly has four empty slots.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
