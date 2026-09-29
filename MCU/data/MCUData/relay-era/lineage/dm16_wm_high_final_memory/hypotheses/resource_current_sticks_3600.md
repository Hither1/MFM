# resource_current_sticks_3600

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 3600
- updated_step: 6600
- depends_on: goal_stone_pickaxe, goal_iron_pickaxe, resource_current_lighting_kit

## Statement

The four-stick stock from step 3651 is stale: two sticks were consumed by the iron-pick recipe and frame 6600 shows no stick stack; new sticks require fresh wood.

## Evidence

- [INV] stick -2 occurred at step 3371, craft_item stone_pickaxe fired at 3390, and frame 3600 shows no stick stack.
- events/events.jsonl records craft_item stick +4 at step 3647, the active 2x2 grid cleared, and logs.txt records [INV] stick +4 at step 3651.
- logs records INV stick -2 during the 6330 recipe; the remaining cursor label was stale, and frames 6495/6600 show no sticks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
