# resource_surface_wood_after_furnace

- kind: resource
- status: active
- confidence: 0.90
- created_step: 3802
- updated_step: 4800
- depends_on: goal_furnace, goal_mine_log, location_live_spawn_spruce_0, location_live_lower_spruce_689

## Statement

Retired as an immediate gate: steps 3953-4779 produced only dirt, grass, leaves, or no break. Wood is useful later but should not delay the first iron ore/ingot milestones.

## Evidence

- At step 3931 the table GUI is open at the surface, the furnace milestone is verified, spruce trunks are visible nearby, and cobblestone x8 remains on the cursor.
- At steps 3953-4017 the first attempt failed because aim_at_tree saw no trunk from the prior angle and chop_tree broke dirt/grass. The current step-4027 frame visibly contains several spruce trunks and the furnace can be placed to free a slot.
- Step-4200 frame shows dense spruce foliage/wood surfaces; events 3993-4108 contain only dirt/grass mining and no log event.
- Steps 3953-4232 repeatedly broke dirt/grass from the current foliage pocket. In contrast, logs.txt verifies spruce-log breaks from (-3007.84,70,-5569.30/-5569.70) at steps 460, 561, and 766, with the lower face acquired at pitch 17 yaw -9.
- The attached step-4412 frame shows a vertical brown spruce trunk beneath the leaf canopy at the left side of the forward view; earlier failures were aimed at grass/leaves or remained out of reach.
- The step-4593 frame clearly shows several full-height bark columns on the opposite grassy bank, unlike the prior leaf/ground-only views.
- [INV] furnace -1 at step 4688 proves the slot was freed; steps 4693-4779 produced no log event, with no-trunk notes and a grass_block break.
- No spruce_log event occurred after step 984; repeated local attempts consumed roughly 1,800 ticks without wood.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
