# location_live_shaft_1200

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 1200
- updated_step: 1800
- depends_on: resource_wooden_pickaxe_secure

## Statement

Refuted as cross-trajectory contamination: this live run stayed at y64 through step 1800 and has no shaft at (-3003.7,56,-5564.3).

## Evidence

- The current map segment holds x/z fixed while y falls from 67 to 56; dig_down events record grass, dirt, and eight stone breaks, and frame 1200 looks down at the shaft floor.
- The final visited.csv trajectory block (row 48002 onward) has minimum y64 through step 1800 and ends at (-2999.08,64,-5563.33); current events contain no stone mining.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
