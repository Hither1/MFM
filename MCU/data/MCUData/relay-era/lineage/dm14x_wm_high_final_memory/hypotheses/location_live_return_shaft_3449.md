# location_live_return_shaft_3449

- kind: location
- status: confirmed
- confidence: 0.95
- created_step: 3449
- updated_step: 4743
- depends_on: location_current_crafting_table, location_return_route_3306, mechanism_pillar_requires_downward_aim

## Statement

The recovered shaft column at block centre (-3004.5,-5566.5) is confirmed traversable to y56: dig_down reached (-3004.38,56.00,-5566.70) at live step 4727 after breaking twelve blocks and descending 14.2 blocks.

## Evidence

- Ground-truth pose matches the earlier shaft coordinates; the route just traversed from the y62 pocket to this point, and the frame shows a tight vertical stone/dirt shaft while looking down.
- Steps 3393-3484 kept the avatar at y64 and produced no dirt use event despite pitch 88 and repeated jump/use. At step 3498 the player moved one block toward the table and the centered frame shows a close dirt face, consistent with a blocked dirt ascent.
- visited.csv fixes the step-3600 pose; the attached frame at pitch -90 shows sky through the dirt-walled shaft, contradicting the earlier overhead-obstruction interpretation.
- Step 3600 at (-3004.42,64,-5566.28) looking up visibly shows the open dirt-walled shaft. The step-3731 ground-truth pose is z=-5564.91, and its pitch-88 frame has the crosshair on the close stone sidewall; repeated jump/use produced no dirt decrement or placement event.
- At steps 3752, 3764, 3784, 3796, and 3816 five dirt use events occurred; the authoritative state moved from y64.00 to y70.25 by step 3823, and the current frame visibly shows the original crafting table nearby.
- Ground-truth events at 4426/4447/4468 verify one grass and two dirt blocks mined while pitch=88; position remained y69 at (-3004.56,-5565.96). The frame shows the newly opened column immediately south of the player's rim footing.
- Live STATE at step 4484 gives x=-3004.52,z=-5566.29 and pitch=88; floor coordinates place the avatar in the block whose centre is (-3004.5,-5566.5), while the attached downward frame shows the dirt floor/shaft opening.
- Live STATE step 4727 and dig_down note: y=56, broke 12 blocks, descended 14.2; subsequent torch placement succeeded at step 4740.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
