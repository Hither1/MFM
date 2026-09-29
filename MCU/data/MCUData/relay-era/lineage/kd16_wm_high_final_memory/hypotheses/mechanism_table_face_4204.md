# mechanism_table_face_4204

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 4204
- updated_step: 4216
- depends_on: goal_crafting_table

## Statement

From position (-3001.7,63.0,-5561.2), absolute pitch -10 and yaw 14 targets the crafting table's exposed clickable face and allows use_until_gui to open it; the geometric look_at target at yaw 25 and pitch 4 does not.

## Evidence

- At this exact pose, look_abs(-10,14) followed by use_until_gui opened the table at step 3991, while look_at(-3002.5,64.5,-5559.5) produced yaw 25/pitch 4 and use_until_gui failed at step 4204.
- At step 4204 look_at toward the stored block centre produced pitch 4/yaw 25, and use_until_gui failed. After look_abs to pitch -10/yaw 14, use_until_gui opened the table at step 4210.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
