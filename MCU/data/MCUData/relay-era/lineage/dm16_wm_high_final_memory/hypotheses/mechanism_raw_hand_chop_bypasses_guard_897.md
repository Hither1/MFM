# mechanism_raw_hand_chop_bypasses_guard_897

- kind: mechanism
- status: refuted
- confidence: 0.10
- created_step: 897
- updated_step: 924
- depends_on: location_live_spawn_spruce_0

## Statement

The raw-attack test did not support a procedure-cutoff explanation: after the step-912 approach, attack broke another spruce leaf at step 924 while no log event occurred, so target occlusion rather than the 75-tick chop guard remains the blocker.

## Evidence

- Frame step_0897 visibly centers brown vertical bark; STATE fixes the pose and aim at pitch -33/yaw -48. events.jsonl records a leaf break at step 839 but no log, and the step-897 note reports the 75-tick chop cutoff.
- events/events.jsonl records mine_block spruce_leaves at step 924 and no spruce_log; STATE remained at (-2998.3,64,-5563.2), and frame 924 shows the crosshair on foliage while a large bark face fills the left side.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
