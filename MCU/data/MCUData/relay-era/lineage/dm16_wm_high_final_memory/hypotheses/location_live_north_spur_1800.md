# location_live_north_spur_1800

- kind: location
- status: stale
- confidence: 1.00
- created_step: 1800
- updated_step: 8400
- depends_on: location_live_shaft_1200

## Statement

The old y55 north spur is stale for live navigation; the current player is in a separate this-run y11 shaft branch at (-3014.70,-5566.30).

## Evidence

- stair_down advanced 2.0 with zero descent; go_to then backtracked 1.66 toward the shaft, and current visited rows extend the same y55 corridor to z=-5561.30.
- Current STATE/map at step 8400 place the player y11, and returning to y55 cannot improve the final milestone.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
