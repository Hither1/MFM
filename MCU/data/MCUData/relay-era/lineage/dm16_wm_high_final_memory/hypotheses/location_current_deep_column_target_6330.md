# location_current_deep_column_target_6330

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 6330
- updated_step: 10200
- depends_on: location_deep_coal_shaft_8840, location_diamond_block_11861, goal_iron_pickaxe

## Statement

The live directed route ends at (-3031.77,12.00,-5558.48), pitch 88/yaw 90 mod 360; the unverified diamond estimate (-3060.5,12.5,-5558.5) lies about 28.7 cells directly west on the same z-line.

## Evidence

- Authoritative STATE at step 7554 is pos=(-3000.7,11.0,-5566.7), pitch=0, yaw=82; events verify the final descent blocks and the held iron pick reports 200/250 uses left.
- visited.csv proves y11 at step 7550 and current pose at 7800; events 7739,7755,7780,7796 verify the branch's first four stone breaks.
- maps/visited.csv last row at 8400 gives the live pose; steps 7724-8400 cover x -3000.70 to -3014.70 while z remains -5566.50 to -5566.30.
- STATE at step 8522 is (-3015.70,11,-5566.30); events verify four stone breaks with the iron pick during the yaw-0 attempt, while mine_forward reports 0.0 blocks advanced and maps/visited.csv shows no x/z movement.
- Last-row map positions trace the shaft at (-3000.70,-5566.70), west branch to x=-3015.7, and exact-yaw-0 corridor to the step-9000 endpoint; frame 9000 shows its plain stone/granite face.
- Last-row-deduplicated visited.csv and steps 9206/9287 redstone events establish the route; step 9580 restored y11 and step 9600 remains at the stated face.
- Ground-truth STATE at step 9792 fixes (-3024.70,12.00,-5558.48); steps 9714, 9746, and 9781 verify three gravel breaks during the short south bypass.
- The last row for step 10200 in maps/visited.csv fixes the pose; event 10197 proves one downward stone break, while no diamond event exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
