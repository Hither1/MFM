# mechanism_dirt_wall_clutch_10923

- kind: mechanism
- status: refuted
- confidence: 0.95
- created_step: 10923
- updated_step: 11400
- depends_on: state_death_drop_10606, location_diamond_depth_shaft_10138, state_second_recovery_death_10923

## Statement

Continuous dirt use during rim entry is not a working recovery clutch: it consumed two dirt and diverted the player from y68 into the same offset y64 pocket without reaching the deep shaft.

## Evidence

- Two unsupported entries were lethal, while dirt is hand-mineable at the y71 respawn and placeable blocks can form protruding ledges against a vertical wall.
- At step 11026 inventory is dirt x3 at y68.5; direct go_to calls failed because the player remained inside the dug pit.
- The step-11055 frame shows the player looking down in a shallow dirt/grass pit with dirt x2; repeated go_to calls failed from inside it, while the earlier surface route succeeded after reaching open ground.
- Steps 11254-11374 moved from the rim through the shaft alignment to y64 while continuous use consumed two dirt; no deep descent occurred, showing early placement altered the entry geometry.
- Steps 11254-11374 and use_item events at 11259/11263 verify two placements, y68→64, and endpoint (-2998.32,64,-5569.70); no pickup occurred.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
