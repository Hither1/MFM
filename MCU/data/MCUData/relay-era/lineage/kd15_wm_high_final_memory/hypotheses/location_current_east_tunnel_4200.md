# location_current_east_tunnel_4200

- kind: location
- status: stale
- confidence: 1.00
- created_step: 4200
- updated_step: 4800
- depends_on: location_current_surface_3733, mechanism_shaft_alignment_9600

## Statement

The step-4200 east face is historical; the live route extended east to x=-2986.30 and descended to y44.

## Evidence

- The later current-run visited.csv row for step 4200 gives the pose; rows 3993-4200 show monotonic eastward advance from x -3005.47, and the frame shows the blocked face.
- Latest-per-step visited rows move from (-3002.30,63,-5567.70) at 4200 to (-2993.30,62,-5567.70) at 4800.
- The final current-reset visited.csv rows show monotonic eastward advance to this pose; step_4200.png shows the blocked tunnel face and no GUI.
- Final current-reset visited rows show monotonic extension and descent through step 4800.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
