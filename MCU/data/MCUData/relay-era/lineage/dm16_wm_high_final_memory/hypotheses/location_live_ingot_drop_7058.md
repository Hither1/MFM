# location_live_ingot_drop_7058

- kind: location
- status: stale
- confidence: 1.00
- created_step: 7118
- updated_step: 8400
- depends_on: goal_iron_ingot, location_surface_furnace_6279

## Statement

The former surface ingot-drop recovery target is stale after the iron-ingot and iron-pickaxe milestones were verified.

## Evidence

- craft_item iron_ingot fired at 7048, INV iron_ingot +1 at 7052 and -1 at 7055, then force-close occurred at 7058 without any later pickup event. visited.csv fixes the close pose; the first sweep crossed the close area during its earliest ticks, before moving roughly two blocks away.
- Ground truth verifies iron_ingot at 5568 and iron_pickaxe at 6330; no surface ingot is needed.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
