# mechanism_stale_craft_cursor_6588

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 6600
- updated_step: 6600
- depends_on: goal_furnace

## Statement

After a recipe consumes its ingredients, the cursor parser can retain the ingredient label even while the real crafted output is banked; craft event plus consumed grid plus inventory gain override that stale label.

## Evidence

- At 6588 craft_item furnace fired and the 3x3 grid was empty while CURSOR still said cobblestonex8; at 6594 [INV] furnace +1 proved the output transfer despite the unchanged label.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
