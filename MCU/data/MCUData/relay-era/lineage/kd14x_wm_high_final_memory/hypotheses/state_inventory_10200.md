# state_inventory_10200

- kind: state
- status: stale
- confidence: 1.00
- created_step: 10200
- updated_step: 4800
- depends_on: goal_stone_pickaxe, goal_iron_pickaxe

## Statement

This step-10200 inventory belongs to another trajectory and is not live in the current reset ending at step 4800.

## Evidence

- Stone-pick events total 122 uses; the attached step-10200 hotbar shows the listed stacks and empty slots; events contain no iron or diamond.
- Step-10800 frame gives a newer authoritative hotbar snapshot.
- Attached step_10200 hotbar crop gives visible stacks; events record iron ore x2 and sand x8 pickups after the prior snapshot.
- Current events and map segment end at 4800 with no iron pick or ore.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
