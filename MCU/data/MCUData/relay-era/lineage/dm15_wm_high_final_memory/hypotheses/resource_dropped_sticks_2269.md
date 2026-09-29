# resource_dropped_sticks_2269

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 2269
- updated_step: 3600
- depends_on: goal_furnace, goal_iron_pickaxe, location_current_crafting_table, resource_current_lighting_kit

## Statement

The old surface stick-drop is no longer a required resource target: three replacement sticks are owned at step 3600, so do not detour for this unverified item entity.

## Evidence

- The step-2269 close_inventory note explicitly reports sticks x2 off-inventory and says they became an item entity on the floor; current STATE has no sticks in inventory.
- craft_item stick +4 at 3104 and frame 3600 shows sticks x3; the old entity has never produced a pickup event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
