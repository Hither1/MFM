# mechanism_table_access_11188

- kind: mechanism
- status: confirmed
- confidence: 0.95
- created_step: 11188
- updated_step: 11317
- depends_on: mechanism_table_face_4204, resource_replacement_stone_pick_10500

## Statement

At surface pose (-3000.98,64,-5561.30), absolute pitch 25 and yaw 32 targets the nearby crafting table and use_until_gui opens its 3x3 screen.

## Evidence

- The step-11188 frame shows a dirt ceiling immediately overhead; prior pillar attempts at steps 10726 and 10950 raised the player one block per cobblestone, while the y62 table interaction failed from below the intervening dirt lip.
- Steps 11239-11260 raised y62 to y64. The original successful table interaction at steps 1887-1892 used the center corresponding to (-3002.5,64.5,-5559.5), while step 11282 retained pitch -10/yaw 14 and failed despite the table being visibly close on the right.
- Step-11305 frame shows the crosshair centered on the grass block immediately right of the visible crafting table after look_at produced pitch 25/yaw 40.
- The 3x3 crafting GUI opened at step 11311 after yaw correction from 40 to 32; step 11314 landed the measured cursor on hotbar slot 1 while it remained open.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
