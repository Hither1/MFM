# location_current_iron_corridor_5400

- kind: location
- status: stale
- confidence: 1.00
- created_step: 5400
- updated_step: 6000
- depends_on: goal_mine_iron_ore

## Statement

The step-5400 corridor snapshot is historical: the player has since advanced north to z=-5581.15 and should no longer use its 10-12-block distance estimate.

## Evidence

- Final-reset maps/visited.csv row 37402 and step_5400.png agree on pose and tunnel view.
- maps/visited.csv records pickup near z=-5582.16 at step 5670, return to z=-5576.3, and the live step-6000 east-shaft pose.
- The final visited.csv segment ends at this coordinate and heading. Events record the east cut's six breaks/2.0 m advance through 5363 and one north-face granite break at 5392 without positional advance.
- Final-reset visited rows move from z=-5568.70 at step 5400 to z=-5581.15 at step 6000.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
