# location_fresh_ingot_drop_8337

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 8400
- updated_step: 9800
- depends_on: goal_iron_ingot, location_y56_furnace_4810

## Statement

The hypothesized recoverable furnace-side iron-ingot entity is absent or expired; retire this location and do not spend more ticks sweeping it.

## Evidence

- The output was clicked before close; craft_item iron_ingot fired on forced close, which then warned that real cursor contents were dropped. visited.csv steps 8338-8400 traces an eastward loop ending at (-3002.95,56,-5566.30), and no pickup event fired.
- Repeated local sweeps culminated in a 72-tick sweep with verified free capacity from the exact interaction pose at step 9216 and produced no pickup.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
