# location_live_spawn_spruce_0

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 161

## Statement

The spawn spruce is reachable from (-3008.31,71.00,-5570.30); yaw -9 and pitch -5 successfully targets a trunk block, and more trunk remains visible immediately ahead.

## Evidence

- The current frame shows multiple spruce trunks, including a broad trunk immediately left of center and another ahead; logs.txt contains only the initial live state.
- At steps 10 and 133 aim_at_tree centered on thousands of bark pixels, while chop_tree twice reached its 75-tick no-break cutoff without movement; the harness explicitly diagnosed out of reach or sky, and the frame clearly shows trunk under the centered crosshair.
- events/events.jsonl verifies spruce_log mine_block at 460 and 561 from nearly unchanged ground-truth position.
- The attached live step-0 frame visibly shows spruce trunks and leaves; current position is (-3009.5,71,-5572.5).
- Ground-truth STATE at step 342 is (-3007.7,70,-5569.4), and the ledger verifies a spruce_log break while the frame shows the remaining trunk above it.
- Live STATE at step 600 plus the three verified mine events and frame 600.
- Live frame visibly shows multiple spruce trunks, and stored prior evidence records successful lower-face targeting at this coordinate and orientation from the same spawn pose.
- Ground-truth state and the step-161 spruce_log mine event confirm the pose and successful geometry; the attached frame shows remaining vertical trunk.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
