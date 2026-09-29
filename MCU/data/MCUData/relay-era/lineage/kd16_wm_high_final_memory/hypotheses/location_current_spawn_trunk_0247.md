# location_current_spawn_trunk_0247

- kind: location
- status: active
- confidence: 0.95
- created_step: 247
- updated_step: 365
- depends_on: location_live_spawn_spruce_0000, tree_final_approach, goal_mine_log

## Statement

The player reached the spawn-side spruce at (-3007.3,69,-5566.3) and broke one log at step 365; remaining spruce wood is visible within the surrounding canopy and should be re-centered after each pickup sweep.

## Evidence

- aim_at_tree centered bark at steps 10 and 132, both following chops timed out after 75 ticks with explicit out-of-reach diagnoses, and the two drop sweeps moved the player about 2.6 blocks closer. The attached step-247 frame still visibly shows the intact trunk ahead.
- Travel moved 7.6 blocks into range, aim_at_tree centered bark, and the following chop generated the verified spruce-log break at step 365.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
