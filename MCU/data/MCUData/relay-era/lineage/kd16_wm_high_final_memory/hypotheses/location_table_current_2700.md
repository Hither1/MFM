# location_table_current_2700

- kind: location
- status: stale
- confidence: 0.10
- created_step: 3000
- updated_step: 3000
- depends_on: goal_crafting_table, location_live_surface_table_ep0000_1157

## Statement

Retired as a non-live branch location: its coordinates and step-4190 opening do not belong to the current step-3000 reset; use location_live_surface_table_ep0000_1157 instead.

## Evidence

- At the old pose (-2999.30,65,-5568.70), pitch 48/yaw -152 opened the table at step 2749; ray geometry intersects the adjacent block centered near (-2998.5,65.5,-5569.5). The current step-4091 pose is (-2998.70,66,-5568.30), within interaction reach.
- At step 4116, look_at(-2998.5,65.5,-5569.5) followed by use_until_gui did not open a screen and the frame showed the table up-left of the dirt crosshair. Logs show use_until_gui opened the table at step 2749 from (-2999.30,65,-5568.70) with pitch 48 yaw -152.
- The step-4139 frame visibly places the table along the far-left edge while the crosshair at pitch 48/yaw -152 is centered on dirt. Comparison with steps 2741 and 3000 shows the same adjacent table/shaft geometry, implying a substantial left-and-up correction from the failed ray.
- Step 4163 frame directly shows the table occupying the left side of view, with its right edge about 10-15 pixels left of the centered crosshair after pitch 30/yaw 172 failed to open it. A small additional left turn should put the crosshair on the table side.
- The step-4182 frame shows the table occupying the left half of view with its right edge near x302 while the crosshair is near x320 at pitch 30/yaw 166. The interaction at yaw 166 failed, confirming the crosshair was still off the table.
- At step 4190, use_until_gui opened the table screen from the stated pose and view after several nearby rays missed.
- Step 4190 use_until_gui opened the 3x3 screen from this exact pose/view; yaw 166 and 172 had missed.
- The current event stream ends before step 3000 and the current table was event-verified from (-3002.65,67,-5568.29) at step 1157, not the later-branch pose in this hypothesis.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
