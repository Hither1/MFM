# location_vertical_stone_column_2245

- kind: location
- status: refuted
- confidence: 0.80
- created_step: 2245
- updated_step: 2344
- depends_on: goal_stone_pickaxe, resource_current_cobblestone

## Statement

The exact floor target at (-3007.3,64,-5559.3) is not a usable vertical descent from the current stance: dig_down broke a coal-ore block but gained no depth because the crosshair carved the nearby face; the exposed eastward face remains useful for coal and stone.

## Evidence

- Step-2245 frame visibly shows stone underfoot/right while the failed stair exposed only dirt ahead; this turn tests the floor with dig_down to y55.
- At step 2344 dig_down reported one block broken, zero descent, and diagnosed wall carving; the authoritative event identifies the broken block as coal_ore at step 2297.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
