# location_corrected_surface_shaft_1727

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 1727
- updated_step: 2400
- depends_on: goal_wooden_pickaxe, resource_wooden_pickaxe_secure

## Statement

The this-run shaft is centred near (-3008.30,-5561.70), reaches y56, and connects there to an east tunnel ending at (-3004.43,56,-5561.30).

## Evidence

- The live frame shows a dirt-lined opening with a stone floor under the crosshair. visited.csv holds the stalled pose near the west/south edge of the same block while prior dig_down broke three adjacent surface blocks without descending.
- final visited.csv trajectory descends at fixed (-3008.30,-5561.70) from y65 to y63; events record stone breaks at 1765/1794 and frame 1800 shows the stone floor.
- Last-per-step map rows show fixed-column descent to y56 at 1997 and eastward advance through 2400; matching stone events prove excavation.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
