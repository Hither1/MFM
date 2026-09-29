# location_return_opening_2966

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 2966
- updated_step: 3600
- depends_on: location_current_crafting_table, location_return_wall_2537, mechanism_pillar_requires_downward_aim, location_live_coal_shaft_2814

## Statement

Refuted for the live run: the claimed reconnection to y64 at step 3352 did not occur; the player remained at the y55 shaft foot.

## Evidence

- Step-2966 and step-3000 frames show the opening aligned toward the stored shaft waypoint; no traversal attempt has yet verified it.
- Authoritative step-3017 state reports 0.00 movement after 50 ticks of forward+jump at yaw -148. The step-3023 zoom shows a one-block raised lip directly beneath a low stone/dirt ceiling.
- Step 3017 gained no movement before clearance. The step-3147 frame shows the same aligned opening after mine_ahead broke two overhead blocks, with pose and yaw unchanged.
- At steps 3147 and 3183, forward+jump at yaw -148 produced exactly 0.00 movement. Step 3095 had already broken two overhead stone blocks, so insufficient ceiling clearance alone is refuted; the attached frame still shows a raised lower face in the doorway.
- The live position stayed fixed through repeated forward-jumps at yaw 212, while the compiled proven route orders the dirt/coal pocket before the newly cut passage ending at the live pose. Reversing yaw points directly toward the previously occupied pocket.
- At step 3306, go_to(-3007.7,-5559.3) moved 1.66 blocks from the dead-end face to (-3007.57,62,-5560.07), confirming the reverse direction. The next plan tests the final 0.8-block approach and pillar ascent.
- Steps 3306-3352 moved from the dead-end at (-3007.3,62,-5561.7) back to the dirt/coal pocket, ascended from y62 to y64 by downward dirt placement, and moved east to (-3005.16,64,-5559.32) with full health; inventory gained two cobblestone during the clearance.
- maps/visited.csv records (-3008.30,55,-5559.70) around step 3352, not the claimed y64 coordinates.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
