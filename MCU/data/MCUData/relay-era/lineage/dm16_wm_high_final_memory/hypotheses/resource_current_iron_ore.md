# resource_current_iron_ore

- kind: resource
- status: confirmed
- confidence: 0.99
- created_step: 7800
- updated_step: 6000
- depends_on: goal_mine_iron_ore, location_iron_candidate_8218, location_live_iron_floor_6282, resource_iron_fuel_gate, location_y56_furnace_4810, location_live_iron_pocket_4800, goal_furnace, location_visible_iron_7717, location_fresh_y55_east_4078, location_surface_furnace_3591

## Statement

Exactly one of the three recovered iron ore remains in the active surface-furnace input after two ingots were produced.

## Evidence

- Pickup iron_ore fired at 7903, no later ore consumption exists, and frame 8600 shows iron ore x1.
- INV iron_ore -1 at 10963 followed by active furnace input and frame 11000 ore/flame; the lingering cursor label is contradicted by inventory and GRID.
- events/events.jsonl records mine_block iron_ore at step 4446 but no later pickup; authoritative step-4455 STATE lists no iron ore because the inventory GUI was opened before collection. Frame step_4446 visibly shows upper and lower exposed ore continuation.
- events verify iron_ore breaks at steps 4446 and 4549 but no pickup; step-4731 STATE still has zero free slots and no iron ore, while frame 4731 clearly shows the remaining tan-speckled floor block.
- Events lines 185/187 verify two iron breaks but no pickup iron_ore through line 192; logs record dirt -3/force-drop at 4740-4743; frame 4800 shows empty cells, the nearby pile, and tan-speckled continuation.
- events/events.jsonl records pickup iron_ore +1 at 4883, +1 at 4885, and +1 at 5006; step-5006 STATE independently reports iron_orex3.
- At step 5256 lifting hotbar slot 0 produced INV iron_ore -3. After landing on furnace input and clicking, the active furnace GRID remained [in] through step 5272 while repeated clicks caused no changes, matching the documented furnace stale-cursor behavior in procedures/smelt_iron_ingot.md.
- Three pickup events fired at 4883/4885/5006; all three were loaded at 5256-5263; ingot crafts fired at 5491 and 5945; frame 6000 shows one input still burning.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
