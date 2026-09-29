# location_live_left_spruce_1443

- kind: location
- status: active
- confidence: 0.75
- created_step: 1443
- updated_step: 1897
- depends_on: goal_crafting_table, goal_mine_log

## Statement

The pond-side spruce is proven reachable, but the step-1800 ray was dirt rather than bark. Ray geometry from the verified step-1513 break places that mined log at block (-2997,65,-5564), so the remaining overhead trunk is most likely the vertically adjacent block centered at (-2996.5,66.5,-5563.5).

## Evidence

- The attached step-1443 frame visibly shows a vertical spruce trunk from screen x≈0-307 beside the player; unlike the prior detector failure, no held log model is present.
- events/events.jsonl verifies mine_block spruce_log at step 1513 and pickup spruce_log at step 1523. The step-1651 frame shows bark occupying the left side while the unchanged yaw -47 ray points through the newly opened gap toward the river, explaining the later miss.
- mine_block spruce_log and pickup fired at steps 1513/1523. The later pitch +5 ray mined grass/dirt at step 1704, while step_1768.png visibly places the remaining log across the upper-left of the frame.
- The same tree yielded mine_block spruce_log at 1513 and pickup at 1523; a 4x crop of frame 1800 visibly places bark and break cracks under the crosshair.
- The fixed pose (-2998.70,64,-5564.70), yaw -47, pitch +11 broke spruce_log at step 1513; intersecting that ray with the west block face gives block (-2997,65,-5564). The later step-1768 frame visibly shows a horizontal underside of log overhead-left. By contrast, the alleged centered bark at step 1800 produced grass_block and dirt events at steps 1806 and 1827, directly refuting that ray.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
