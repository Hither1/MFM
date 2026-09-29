# location_current_east_face_4800

- kind: location
- status: stale
- confidence: 1.00
- created_step: 4800
- updated_step: 5400
- depends_on: goal_mine_iron_ore

## Statement

The step-4800 east-face pose is historical; the tunnel reached the north iron recess and the player later withdrew south.

## Evidence

- Authoritative latest visited row and step-4800 frame; z remains -5567.70 throughout the corridor.
- Latest-per-step visited rows put the live player at (-2989.65,63.25,-5567.68) at step 5400.
- The last authoritative visited.csv row for step 4800 and the attached frame agree; duplicate earlier rows for step 4800 belong to superseded trajectories.
- Step-5302 mine_forward reports 5.7 blocks advanced then two no-move cycles; visited.csv subsequently descends at x=-2985.30 to y56 by step 5400.
- The final current-reset visited.csv segment ends at this pose for steps 4771-4800; the attached frame shows the dark blocked north face. The prior y62 claim came from an earlier reset segment.
- Final-reset visited rows reach z=-5581.70 and end at (-2986.70,44,-5578.43).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
