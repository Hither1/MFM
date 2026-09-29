# mechanism_south_leg_stall_8522

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 8522
- updated_step: 9000
- depends_on: location_current_deep_column_target_6330, mechanism_axis_aligned_mine_forward_8400

## Statement

The yaw-0/yaw-5 stall was lateral wall clipping, not a solid route: shifting 0.65 block from x=-3015.95 to x=-3015.30 enabled exact-yaw-0 mining to advance 11 cells.

## Evidence

- The step-8522 mine_forward note reports four blocks broken, zero blocks advanced, and an early stop after two non-advancing cycles.
- The step-8522 yaw-0 attempt broke four blocks and advanced 0.0. The step-8634 yaw-5 attempt again broke four blocks and advanced only 0.2, ending at (-3015.94,11,-5566.30); the attached frame is dominated by the close right-hand wall, supporting side-wall clipping.
- Two attempts broke eight blocks but advanced only 0.24 cell; the six-tick left strafe at step 8641 centred the avatar, after which maps show 11 cells of +z progress through step 9000.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
