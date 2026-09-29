# mechanism_furnace_top_aim_5695

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 5695
- updated_step: 5707
- depends_on: location_surface_furnace_3591, resource_iron_fuel_gate

## Statement

From the live pose (-3006.72,70.00,-5569.25), targeting the furnace upper top face near (-3007.5,69.9,-5567.5) provides a valid interaction ray; the GUI opened immediately after this corrected aim.

## Evidence

- A 4x crop of step_5695 shows the crosshair exactly on the grass/furnace boundary, explaining three no-GUI interaction attempts despite correct horizontal heading.
- Steps 5696-5701: look_at the upper top face followed by use_until_gui opened the furnace; GUI open=True and the active furnace GRID retained its input.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
