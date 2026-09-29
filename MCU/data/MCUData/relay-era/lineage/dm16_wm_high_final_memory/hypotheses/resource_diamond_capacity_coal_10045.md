# resource_diamond_capacity_coal_10045

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 10045
- updated_step: 10200
- depends_on: goal_diamond, resource_diamond_capacity_redstone_9600

## Statement

The coal-disposal attempt is historical and superseded: coal was removed at 10070-10073 but its slot immediately filled; the later eastward andesite drop now provides durable diamond capacity.

## Evidence

- Step 10045 STATE reports zero free slots, coal x1 in hotbar.8, and andesite x2 present again; [INV] andesite +2 at step 9845 proves the earlier drop was reclaimed. The redstone force-drop mechanism succeeded at 9683-9686, and immediate westward movement can leave coal behind.
- [INV] coal -1 at step 10070 and the forced-close note at 10073 verify removal; STATE at 10157 reports no coal and zero free slots after cobblestone pickups.
- Step 10157 had no free slot after coal removal; [INV] andesite -2 at 10172 and frame 10200 with two empty hotbar cells resolve the current gate.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
