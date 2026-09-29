# location_south_level_tunnel_7200

- kind: location
- status: refuted
- confidence: 0.98
- created_step: 7200
- updated_step: 8278
- depends_on: location_midcorridor_bounded_shaft_6683, goal_mine_iron_ore

## Statement

The y60 south tunnel at x=-3004.3 reaches a water opening near z=-5541.3; the current pushed-back face is flooded and no longer a productive straight mining route.

## Evidence

- Steps 7101-7198 verify five stone breaks; maps/visited.csv shows 1.0 block southward advance by step 7200, and no iron event yet.
- maps/visited.csv steps 7047-7800; strip_mine advanced 5.0 blocks in 320 ticks, 6.2 in 280, and 1.28 in the latest 64.
- At steps 8148-8278, after opening the face near z=-5541.3, strip_mine broke three blocks but advanced only 0.4 and stopped after two no-movement cycles; state moved north to z=-5545.59 and the frame visibly shows flowing water.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
