# location_current_surface_10800

- kind: location
- status: stale
- confidence: 1.00
- created_step: 10800
- updated_step: 4800
- depends_on: mechanism_cobble_pillar_return_10606, location_diamond_depth_shaft_10138

## Statement

The step-10800 surface location belongs to another trajectory; the live player is underground at (-2986.30,44,-5576.70).

## Evidence

- visited.csv step 10800 and the attached frame; verified table pose is (-3001.7,63,-5561.2).
- maps/visited.csv fixes step 11400 at (-3000.98,64,-5561.30), not the old y62 trench.
- maps/visited.csv repeats this pose from steps 10746-10800; attached frame shows the enclosing dirt/grass geometry.
- Final current-reset visited row at step 4800 gives the underground pose.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
