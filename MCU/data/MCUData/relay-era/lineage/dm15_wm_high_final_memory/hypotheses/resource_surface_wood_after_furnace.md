# resource_surface_wood_after_furnace

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 3802
- updated_step: 6712
- depends_on: goal_furnace, goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689

## Statement

The step-6574 spawn-grove spruce drop was recovered at live step 6712; the player now owns one spruce log in hotbar slot 6, enough to craft four planks for iron-pick sticks and furnace fuel.

## Evidence

- Steps 3953-4232 repeatedly broke dirt/grass from the current foliage pocket. In contrast, logs.txt verifies spruce-log breaks from (-3007.84,70,-5569.30/-5569.70) at steps 460, 561, and 766, with the lower face acquired at pitch 17 yaw -9.
- The attached step-4412 frame shows a vertical brown spruce trunk beneath the leaf canopy at the left side of the forward view; earlier failures were aimed at grass/leaves or remained out of reach.
- The step-4593 frame clearly shows several full-height bark columns on the opposite grassy bank, unlike the prior leaf/ground-only views.
- [INV] furnace -1 at step 4688 proves the slot was freed; steps 4693-4779 produced no log event, with no-trunk notes and a grass_block break.
- No spruce_log event occurred after step 984; repeated local attempts consumed roughly 1,800 ticks without wood.
- At step 6000 furnace is verified and two ore are owned, but current-prefix events/HUD show no coal, log, plank, or stick; the permanent registry supplies proven nearby spruce approaches.
- events line 372 verifies mine_block spruce_log at 6574 from (-3008.06,70,-5569.70), pitch/yaw 17/-9; events through 6600 contain no pickup spruce_log and current pose is only 1.74 blocks away.
- logs.txt at step 6712 records [INV] spruce_log +1 and events/events.jsonl records pickup spruce_log +1; authoritative STATE lists spruce_logx1 in hotbar slot 6.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
