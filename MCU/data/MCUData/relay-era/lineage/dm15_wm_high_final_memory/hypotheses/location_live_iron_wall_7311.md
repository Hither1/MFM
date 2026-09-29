# location_live_iron_wall_7311

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 7311
- updated_step: 6000
- depends_on: location_return_gap_6946, goal_mine_iron_ore, resource_current_iron_ore

## Statement

The iron face directly north of (-2993.3,55,-5564.7) was verified and mined this run at step 5774; its ore was picked up at 5784 and is now smelting. Retire further local iron search for this run, while retaining the site in the permanent registry.

## Evidence

- At live step 7311 the ore watcher stopped mine_ahead and saved step_7311_ore.png after detecting a 15-pixel speckle cluster at screen coordinate (247,16); the attached lit frame visibly shows tan speckles embedded in grey stone on the upper-left wall.
- The attached live step-7450 frame visibly shows tan iron speckles across a stone block on the left wall, and the preceding collect_drops moved the player 1.16 blocks west into the opened corridor.
- The step-7462 ore-stop frame and a 4x crop clearly show tan iron speckles in stone at screen coordinate about (251,211), while the crosshair is near (320,180).
- mine_block iron_ore fired at 7490/7519 and pickup iron_ore fired at 7500/7529 after the manual left/down alignment.
- Inherited ground truth recorded mine_block iron_ore at 7490/7519 and pickups at 7500/7529; reset restores natural ore.
- At step 5693 mine_forward stopped on iron-like speckles at screen (288,197). A 4x crop of the flag-time frame clearly shows the characteristic tan-speckled iron texture filling the nearby floor/wall face; current pose is (-2993.3,55,-5564.7), pitch 35, yaw 180. This is a materially different direct visual test after the prior GUI-blocked approach made no world attempt.
- Ore-stop frame 5693 visually showed iron; mine_block iron_ore fired at 5774, pickup at 5784, and step 6000 shows that ore in furnace input.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
