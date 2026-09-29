# mechanism_diamond_drop_pocket_10800

- kind: mechanism
- status: stale
- confidence: 1.00
- created_step: 10800
- updated_step: 10800
- depends_on: location_diamond_vein_10362

## Statement

The trapped-diamond-drop claim belongs to another trajectory and is stale here; no diamond ore has yet broken in the live event stream.

## Evidence

- After three ore breaks the player stayed within 0.4 block of the original pose; four 24-tick sweeps yielded no pickup, while step_10797 visibly shows a trench, floating cobblestone ahead, and intact diamond ore on the right wall.
- Empty sweeps ended at 10962, 11093, and 11269 despite opened capacity; the intact west-wall diamond remained visible and the prior left strafe moved east, away from it.
- Current events end at step 10792 with ordinary stone and contain no mine_block diamond_ore or pickup diamond; current pose is still east of the pocket.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
