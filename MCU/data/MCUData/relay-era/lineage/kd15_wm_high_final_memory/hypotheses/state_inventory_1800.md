# state_inventory_1800

- kind: state
- status: refuted
- confidence: 1.00
- created_step: 1800
- updated_step: 1800
- depends_on: goal_wooden_pickaxe, goal_crafting_table

## Statement

Refuted as an ancestor snapshot: the live step-1800 inventory is table x1 and log x1, not dirt, sticks, or a wooden pickaxe.

## Evidence

- The step-1800 hotbar visibly shows dirt x6, wooden pickaxe, and sticks x2; events through 1800 contain no stone, cobblestone, iron, or diamond event, and 11 pick uses imply about 48/59 remaining.
- Events and inventory changes from steps 1848-2399 supersede the old dirt/pick/stick-only snapshot.
- The authoritative current event file has no stick or wooden-pickaxe craft; frame 1800 shows only the table and log stacks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
