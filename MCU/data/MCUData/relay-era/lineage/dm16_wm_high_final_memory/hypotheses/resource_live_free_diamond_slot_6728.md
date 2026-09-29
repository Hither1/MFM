# resource_live_free_diamond_slot_6728

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 6728
- updated_step: 7800
- depends_on: goal_iron_pickaxe, goal_diamond

## Statement

Refuted and retired: the earlier forced dirt drop did not create persistent capacity because all three dirt were recollected during shaft opening; empty-looking HUD cells are not usable free slots in the restricted inventory.

## Evidence

- Live step 6728 reports zero free slots but identifies dirt x3 in zero-based hotbar slot 4; forced GUI close can drop that exact lifted stack, and the following go_to moves about five blocks away before pickup delay expires.
- Pickup dirt events fired at 6828, 6849, and 6870 after the forced drop; frame 7200 shows dirt x3 and empty slots.
- Dirt pickups at 6828/6849/6870 reversed the step-6740 drop, and the later pillar cycle again ends with dirt x3 and zero usable free capacity.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
