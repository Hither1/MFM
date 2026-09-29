# resource_surface_table_recovery_11396

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 11396
- updated_step: 5400
- depends_on: goal_crafting_table, resource_rebuild_stone_pick_7259, goal_stone_pickaxe, resource_iron_fuel_gate, resource_current_cobblestone, location_current_crafting_table

## Statement

Refuted as future-trajectory contamination; the current table remains placed and unopened since 714, although its coordinate is known.

## Evidence

- At step 11396 the player is at (-3004.7,68.0,-5567.4), within reach of the stored table coordinate, with 57 cobblestone and 3 sticks but no pickaxe.
- Authoritative step-11557 state lists cobblestone x57 and sticks x3; attached frame visibly centers the adjacent crafting table, and the verified craft_stone_pickaxe procedure supplies the recipe sequence.
- use_until_gui opened the table at 11562 from (-3002.75,67,-5566.17); GRID at 11591 shows cells 0,1,2 and out FULL, INV returned 49 cobblestone, and INV stick -3 at 11597; attached step-11600 frame shows slab output and sticks on cursor.
- No current table mine/pickup/use after 714 exists and step 11396 is outside the prefix.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
