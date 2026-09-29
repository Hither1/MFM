# location_diagonal_fallback_9752

- kind: location
- status: refuted
- confidence: 0.90
- created_step: 9752
- updated_step: 9890
- depends_on: location_west_face_9455, goal_mine_iron_ore

## Statement

The yaw-130 diagonal staircase from the old corridor is not a productive descent: it broke four ordinary stone blocks but advanced only 0.5 block and descended 0.1 before a verified stall.

## Evidence

- The current west endpoint is reachable, but cardinal north/east/west faces around the y60 spine repeatedly stalled. A diagonal heading from the retreat point has not been tested and a three-level staircase bounds durability cost.
- At steps 9816-9887 stair_down broke four stone blocks; at step 9890 its note reported advanced 0.5, descended 0.1, and stopped early after 96 ticks without depth gain.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
