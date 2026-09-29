# resource_iron_ore_drop_6296

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 6528
- updated_step: 7403
- depends_on: goal_mine_iron_ore

## Statement

The live reset now holds iron_ore x3 in zero-based hotbar slot 3 at step 7403, sufficient for the three-ingot batch once the furnace is opened and fueled.

## Evidence

- events/events.jsonl verifies iron_ore mine_block events at steps 6296, 6335, and 6364, while every subsequent STATE through 6528 has zero free slots and no iron ore inventory stack.
- Events verify three iron breaks and no iron pickup; step-6600 hotbar shows two empty cells. Prior sweeps stopped on cobble or moved south.
- events/events.jsonl records pickup iron_ore at steps 6866 and 6871, and the authoritative step-6952 inventory reports iron_ore x2.
- events/events.jsonl records iron_ore pickups for the two recovered drops and the step-7042 block; authoritative step-7103 inventory reports iron_ore x3.
- The step-6623 event stream ends with mine_block iron_ore and no pickup iron_ore, while STATE reports 0 slots free and crafting_table x1 in hotbar slot 4.
- Current events verify three iron_ore breaks but only pickups at 6651 and 6728; authoritative step-6846 inventory is iron_ore x2, and the attached frame visibly exposes ore along the left wall/floor.
- Current events verify three iron-ore breaks and pickups only at steps 6651 and 6728; authoritative step 7093 inventory is iron_ore x2, while frame step_7093.png shows tan-flecked iron under the crosshair.
- events/events.jsonl records the third pickup at step 7193, and authoritative step-7403 inventory reports iron_ore x3.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
