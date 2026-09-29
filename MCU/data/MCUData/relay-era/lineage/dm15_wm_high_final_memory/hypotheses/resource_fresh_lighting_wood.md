# resource_fresh_lighting_wood

- kind: resource
- status: refuted
- confidence: 0.97
- created_step: 4322
- updated_step: 4800
- depends_on: goal_mine_log, goal_mine_iron_ore

## Statement

The claimed directly harvestable spruce trunk near (-3006,-5568) at yaw -146 is not a valid block target from the current forest pocket.

## Evidence

- At step 4322 the player is healthy at (-3008.55,70.0,-5564.72), only 1.9 horizontal blocks from the coordinates where spruce logs were successfully broken and collected at steps 419-706; the current frame shows nearby spruce trunks and an overhead log.
- At step 4497 the player is at (-3007.8,70.0,-5565.7), and the attached frame clearly shows a thick lower spruce trunk on the right at apparent chopping range. Earlier aim_at_tree at this site recognized bark but was centered low enough to mine grass, so this test first raises pitch and turns directly onto the visible lower face.
- At step 4668 the close trunk occupies the far-right edge while facing yaw -177 from (-3007.65,69.54,-5566.80); screen geometry places it about 30 degrees right, near yaw -146, and within roughly three blocks.
- Tests through step 4800 contradicted the target: yaw -146/pitch +18 broke grass at 4720, yaw -146/pitch -5 broke spruce leaves by 4736, and repeated detector-centred 75-tick chops at nearby poses broke nothing. No spruce_log event occurred after step 682.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
