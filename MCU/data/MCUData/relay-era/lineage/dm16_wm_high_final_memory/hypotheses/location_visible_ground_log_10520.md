# location_visible_ground_log_10520

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 10520
- updated_step: 11000
- depends_on: location_live_trunk_view_9800

## Statement

The overhead spruce face near (-3000.7,65,-5569.7) was valid: pitch/yaw -12/-109 broke a spruce log at step 10747; the targeted block is exhausted this run.

## Evidence

- Zoomed frame 10520 shows a rectangular bark face spanning roughly x333-370 while the crosshair is at x320; the object also appears to block forward motion.
- A 4x crop of step_10676 shows the log face spanning the central upper view, with its underside about 100 source pixels above the crosshair; the prior +8-degree yaw shift targeted grass and is superseded by this vertical correction.
- events/events.jsonl line 501 records mine_block spruce_log at step 10747 after the vertical correction.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
