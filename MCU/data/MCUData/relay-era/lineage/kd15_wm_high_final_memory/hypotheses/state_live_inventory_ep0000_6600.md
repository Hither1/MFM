# state_live_inventory_ep0000_6600

- kind: state
- status: stale
- confidence: 1.00
- created_step: 6600
- updated_step: 8338
- depends_on: goal_furnace, goal_stone_pickaxe, state_live_inventory_ep0000_8338

## Statement

The step-6600 inventory snapshot is historical and superseded by state_live_inventory_ep0000_8338; it must not be used as the live inventory.

## Evidence

- The step-6600 hotbar visibly shows furnace and one empty slot; events total 68 stone-pick uses and contain no use_item furnace after its craft, proving 63 durability and no placement.
- Steps 6669-8338 added iron ore, an ingot, furnace placement/recovery, extensive mined blocks, and pillar consumption; frame 8338 is the newer authoritative snapshot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
