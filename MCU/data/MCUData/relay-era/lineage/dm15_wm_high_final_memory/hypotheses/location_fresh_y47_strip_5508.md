# location_fresh_y47_strip_5508

- kind: location
- status: confirmed
- confidence: 0.95
- created_step: 5508
- updated_step: 6055
- depends_on: location_fresh_iron_strip_5041, mechanism_manual_front_block_5285, goal_stone_pickaxe

## Statement

The north strip began traversably from the y47 shaft foot, but its continuation descended unexpectedly to y41 and inflicted 3 fall damage near (-2988.5,41,-5543.4); do not continue north without first resolving the drop geometry.

## Evidence

- The same shaft safely descended eight blocks from y65 to y57 in 155 ticks, whereas every yaw-90 continuation at y57 stalled. Iron remains valid below y63.
- At step 5621 dig_down broke three blocks but descended 0.0 and explicitly diagnosed that the avatar was not on the shaft center. The same center previously supported a safe y65-to-y57 descent.
- The step-5825 dig_down note verifies 10 blocks broken and 10.0 blocks descended, reaching its y47 target. Step 5828 verifies the player stationary at that coordinate, pitch 0 and yaw 0, with a stone wall directly ahead and 69/131 stone-pick uses left.
- visited.csv steps 5825-6000 verifies the coordinate path; events 5847-5996 contain seven stone breaks and no iron event.
- The step-6055 strip_mine result moved 4.16 blocks while y fell from 47 to 41, then the harness interrupted on 3 damage at (-2989,41,-5543). Events through 6053 show only stone/cobblestone and no iron.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
