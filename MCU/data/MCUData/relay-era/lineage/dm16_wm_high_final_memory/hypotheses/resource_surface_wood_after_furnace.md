# resource_surface_wood_after_furnace

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 3802
- updated_step: 8400
- depends_on: goal_furnace, goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689

## Statement

Surface wood acquisition is retired for this run: all crafting gates are complete and returning from y11 cannot advance the sole diamond milestone within budget.

## Evidence

- The step-4593 frame clearly shows several full-height bark columns on the opposite grassy bank, unlike the prior leaf/ground-only views.
- [INV] furnace -1 at step 4688 proves the slot was freed; steps 4693-4779 produced no log event, with no-trunk notes and a grass_block break.
- No spruce_log event occurred after step 984; repeated local attempts consumed roughly 1,800 ticks without wood.
- At step 6000 furnace is verified and two ore are owned, but current-prefix events/HUD show no coal, log, plank, or stick; the permanent registry supplies proven nearby spruce approaches.
- events line 372 verifies mine_block spruce_log at 6574 from (-3008.06,70,-5569.70), pitch/yaw 17/-9; events through 6600 contain no pickup spruce_log and current pose is only 1.74 blocks away.
- logs.txt at step 6712 records [INV] spruce_log +1 and events/events.jsonl records pickup spruce_log +1; authoritative STATE lists spruce_logx1 in hotbar slot 6.
- Current events ends with mine_block grass_block at 6580 and has no post-iron-pick spruce-log event or pickup; the prior step-6712 claim is beyond the live horizon.
- At step 8400 the score is 9/10, the player is y11 with an iron pick, and only diamond pickup remains.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
