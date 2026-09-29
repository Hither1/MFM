# location_east_level_branch_8278

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 8278
- updated_step: 8400
- depends_on: location_south_level_tunnel_7200

## Statement

The eastbound y60 branch attempted from (-3004.3,-5545.5) lies in the flooded zone and is not a productive mining route.

## Evidence

- The perpendicular wall at the current pushed-back position has not been mined; turning east avoids re-testing the water-blocked south face.
- At step 8291 the player is aligned yaw -90 against an apparently solid dirt/stone face; the prior 13-step attempt only turned and settled, so this face remains untested by actual mining.
- At yaw -90, steps 8314, 8338, and 8377 broke dirt, but maps/visited.csv shows x fixed at -3004.30 while z drifted from -5545.47 to -5547.07 by step 8400.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
