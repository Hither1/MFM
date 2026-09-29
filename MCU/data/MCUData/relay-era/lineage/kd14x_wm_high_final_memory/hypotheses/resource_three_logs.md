# resource_three_logs

- kind: resource
- status: stale
- confidence: 0.99
- created_step: 622
- updated_step: 600
- depends_on: goal_mine_log

## Statement

The prior expedition's confirmed three-log reserve is historical and does not describe the reset inventory.

## Evidence

- One log has broken on the current ray; the current frame still shows trunk wood behind the crosshair, and the first drop remains nearby.
- Two spruce logs are held at step 917, two logs have already been broken from this nearby trunk, and another spruce wood face is visible at the upper-right of the current frame.
- craft_item spruce_planks fired twice at steps 1097 and 1102; current authoritative inventory is four spruce planks plus one crafting table, with no logs.
- Pickup spruce_log occurred only at steps 632 and 708; craft_item spruce_planks +4 occurred twice; inventory then held four planks and one table.
- Authoritative inventory at step 1775 contains spruce_log x1 and spruce_planks x4; events record the new log mine and pickup.
- Verified mine, pickup, and craft_item events at steps 1765, 1775, and 1799.
- Live hotbar is empty at step 600 and events show no pickup; reset explicitly removed inventory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
