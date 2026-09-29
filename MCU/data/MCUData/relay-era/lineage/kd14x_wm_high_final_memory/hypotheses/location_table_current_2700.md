# location_table_current_2700

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 4200
- depends_on: goal_crafting_table

## Statement

The placed crafting table is adjacent to the shaft and is proven openable from (-2998.70,65.00,-5568.30) at pitch 30, yaw 160 with a non-placeable item selected.

## Evidence

- Step 2700 records crafting_table -1 during place_block from the live pose; table GUI interactions then succeed through step 2971 from the same pose, and the step-3000 frame visibly shows the table adjoining the player.
- At the old pose (-2999.30,65,-5568.70), pitch 48/yaw -152 opened the table at step 2749; ray geometry intersects the adjacent block centered near (-2998.5,65.5,-5569.5). The current step-4091 pose is (-2998.70,66,-5568.30), within interaction reach.
- At step 4116, look_at(-2998.5,65.5,-5569.5) followed by use_until_gui did not open a screen and the frame showed the table up-left of the dirt crosshair. Logs show use_until_gui opened the table at step 2749 from (-2999.30,65,-5568.70) with pitch 48 yaw -152.
- The step-4139 frame visibly places the table along the far-left edge while the crosshair at pitch 48/yaw -152 is centered on dirt. Comparison with steps 2741 and 3000 shows the same adjacent table/shaft geometry, implying a substantial left-and-up correction from the failed ray.
- Step 4163 frame directly shows the table occupying the left side of view, with its right edge about 10-15 pixels left of the centered crosshair after pitch 30/yaw 172 failed to open it. A small additional left turn should put the crosshair on the table side.
- The step-4182 frame shows the table occupying the left half of view with its right edge near x302 while the crosshair is near x320 at pitch 30/yaw 166. The interaction at yaw 166 failed, confirming the crosshair was still off the table.
- At step 4190, use_until_gui opened the table screen from the stated pose and view after several nearby rays missed.
- Step 4190 use_until_gui opened the 3x3 screen from this exact pose/view; yaw 166 and 172 had missed.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
