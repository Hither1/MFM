# goal_iron_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 9555
- depends_on: goal_iron_ingot, goal_crafting_table, resource_iron_ore_drop_6296

## Statement

The live reset crafted the iron pickaxe at step 9550 and banked it in zero-based hotbar slot 2 at step 9555; both the craft_item statistic and milestone are verified.

## Evidence

- At step 7800 the furnace GUI is open with cursor empty over output; frame and relevant GRID show output x2, inventory accounting shows iron_ingot x1 and sticks x4, and events contain no iron-pick craft yet.
- events/events.jsonl records milestone iron_pickaxe and craft_item iron_pickaxe +1 at step 7905; the live 3x3 grid is empty after output pickup and the cursor is over empty hotbar slot 5.
- events/events.jsonl verifies milestone and craft_item iron_pickaxe at 7905; logs records [INV] iron_pickaxe +1 at 7910; the step-8400 hotbar shows it in the sixth slot.
- Current events contain no craft_item iron_pickaxe.
- At step 9432 pickup iron_ingot +3 verified; craft_item stick +4 fired at step 9473 and [INV] stick +4 at 9477. Step 9480 has an empty relevant 2x2 grid but a stale spruce_planks cursor label, matching the proven safe force-close condition.
- At step 9519 the authoritative open-table state reports inventory stick x4, no inventory iron ingots, and [GRID] 3x3 cells 0,1,2 occupied after the three paired ingot placements; no craft_item iron_pickaxe event exists yet.
- events/events.jsonl records milestone iron_pickaxe and craft_item iron_pickaxe +1 at step 9550; the authoritative 3x3 grid is empty and the cursor is landed over empty hotbar slot 2.
- events/events.jsonl verifies craft_item and milestone iron_pickaxe at step 9550; the step-9555 inventory delta records iron_pickaxe +1 and the authoritative hotbar places it in zero-based slot 2.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
