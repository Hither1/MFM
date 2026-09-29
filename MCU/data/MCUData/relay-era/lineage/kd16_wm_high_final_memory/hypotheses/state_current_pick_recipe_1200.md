# state_current_pick_recipe_1200

- kind: state
- status: stale
- confidence: 1.00
- created_step: 1200
- updated_step: 1800
- depends_on: goal_crafting_table

## Statement

The step-1200 open wooden-pickaxe recipe is historical and resolved: the craft and milestone fired at step 1224 and the output was banked at step 1229.

## Evidence

- Logs record spruce_planks -6 at 1172, three right-click placements, spruce_planks +3 at 1195, then cursor_to_slot(1) without a click; step_1200.png visibly shows the top row, x3 plank stack, stick slot, and six-slab output.
- events/events.jsonl records craft_item wooden_pickaxe and milestone at step 1224; logs.txt records [INV] wooden_pickaxe +1 at step 1229 and GUI closed at 1232.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
