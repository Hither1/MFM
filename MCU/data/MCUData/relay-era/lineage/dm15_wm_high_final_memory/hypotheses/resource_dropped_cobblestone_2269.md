# resource_dropped_cobblestone_2269

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 2269
- updated_step: 2400
- depends_on: goal_furnace, location_current_crafting_table, goal_stone_pickaxe

## Statement

Refuted: no real cobblestone/stick cache was dropped at 2269; the reported 11 cobblestone and two sticks exactly equal inputs already consumed by the stone-pick and furnace recipes.

## Evidence

- The step-2269 close_inventory note explicitly reports cobblestone x11 off-inventory and says it became an item entity on the floor; current STATE retains only cobblestone x1.
- The real 3x3 grid was empty, two sweeps through step 2341 produced no pickup, and frame 2400 retains only the legitimate one-cobblestone remainder with no sticks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
