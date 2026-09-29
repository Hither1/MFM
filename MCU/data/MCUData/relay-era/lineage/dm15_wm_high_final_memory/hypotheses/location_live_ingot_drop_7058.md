# location_live_ingot_drop_7058

- kind: location
- status: active
- confidence: 0.85
- created_step: 7118
- updated_step: 7118
- depends_on: goal_iron_ingot, location_surface_furnace_6279

## Statement

The first live-run iron ingot was deliberately dropped when the furnace screen force-closed at step 7058 from pose (-3006.87,69,-5566.30); it should remain recoverable on or immediately beside that elevated furnace tile after the pickup delay.

## Evidence

- craft_item iron_ingot fired at 7048, INV iron_ingot +1 at 7052 and -1 at 7055, then force-close occurred at 7058 without any later pickup event. visited.csv fixes the close pose; the first sweep crossed the close area during its earliest ticks, before moving roughly two blocks away.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
