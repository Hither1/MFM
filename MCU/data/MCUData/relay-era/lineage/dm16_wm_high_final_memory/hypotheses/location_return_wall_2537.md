# location_return_wall_2537

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2537
- updated_step: 3000
- depends_on: location_current_crafting_table

## Statement

The y66 return obstruction is resolved this run: a final dirt placement and forward-jump connected the shaft pillar to surface y69, so it is no longer the live route blocker.

## Evidence

- Three closed-loop go_to attempts stopped after only 0.4 blocks and reported a wall/pit/tree obstruction; the step-2537 frame shows stone directly ahead and dirt at right.
- Ground-truth states moved from z=-5559.7 at step 2537 to z=-5561.7 at step 2825; mine_forward reported eight blocks broken and inventory gained seven cobblestone across the passage work.
- Mining through step 2966 moved about two blocks and exposed the opening, while prior go_to calls remained blocked.
- Steps 2640-2671 show a peak at y67.25, a fall to y66, and a close dirt face while aimed north toward the saved table; current INV has exactly 13 cobblestone and one dirt.
- At steps 2672-2792, 120 ticks of attack+forward+jump aimed north at pitch -35 produced no mine event and no horizontal movement, while y briefly peaks near 67 before falling to 66. The current frame is dirt-lined at point-blank range, and prior verified low-ceiling routes only became traversable after overhead mining.
- use_item dirt fired at step 2920; STATE then reached (-3008.06,69.25,-5561.81) at 2948 and go_to advanced 2.9 blocks to the worksite by 2964.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
