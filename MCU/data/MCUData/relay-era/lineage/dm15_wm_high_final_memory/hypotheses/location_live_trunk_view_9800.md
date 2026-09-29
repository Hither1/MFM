# location_live_trunk_view_9800

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 9800
- updated_step: 11000

## Statement

The spruce face alignment near (-3000.3,65,-5569.7) was valid: pitch/yaw -10/-103 broke a spruce log at step 10413; the targeted block is exhausted this run.

## Evidence

- The final map row fixes pose (-3000.30,65,-5569.70), pitch/yaw -50.3/-48.4, while frame 9800 visibly shows bark at left and sky under the crosshair.
- Frame 10031 still shows the trunk at extreme left. At step 9884 aim_at_tree reported no trunk detected and did not move the camera; the following chop broke dirt rather than wood.
- Frame 10182 visibly places bark at eye height from x=0..205 while the crosshair is centered at yaw -78; shifting about 18 degrees left should center the face. The prior failures kept this bark peripheral or targeted disproven overhead coordinates.
- Map rows 10343-10400 hold the pose and yaw fixed, while frame 10400 visibly shows bark filling the centre with the crosshair on it; the earlier yaw -96 attempt missed, and the seven-degree correction created the present alignment.
- events/events.jsonl line 499 records mine_block spruce_log at step 10413 immediately after the aligned chop.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
