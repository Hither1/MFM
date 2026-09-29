# location_fresh_spawn_spruce_0

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 480
- depends_on: location_live_spawn_spruce_0

## Statement

The spawn-grove spruce trunk is reachable from (-3008.28,70.00,-5569.30) at pitch 6, yaw -18, and the post-break frame shows more trunk still centered for continued harvesting.

## Evidence

- Attached step_0000 frame shows spruce bark columns ahead amid leaves; live STATE gives the observation pose.
- At steps 10 and 133 aim_at_tree centered 2742-2751 bark pixels at yaw -15, but chop_tree timed out after 75 ticks at steps 85 and 208 with no event and essentially no movement; the current frame still shows the centered trunk.
- Ground-truth STATE fixes the pose and aim; mine_block spruce_log fired at step 480 and the attached step-480 frame visibly shows remaining centered bark.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
