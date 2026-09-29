# location_live_table_ep0000_7905

- kind: location
- status: active
- confidence: 0.70
- created_step: 7905
- updated_step: 8400
- depends_on: goal_crafting_table, goal_iron_pickaxe

## Statement

The current-reset crafting table was proven openable near claimed center (-3004.5,68.5,-5566.5), but the step-7974 mining attempt on that ray broke nothing and collected no drop; it probably remains at the surface worksite, while its exact break ray is unresolved.

## Evidence

- At steps 7841-7846, look_at this exact center from (-3004.51,68.00,-5568.46) followed by use_until_gui opened the 3x3 crafting-table screen; the iron-pick craft at step 7905 leaves the same pose and aim.
- use_until_gui opened its 3x3 screen at 7846, but mine_ahead at 7974 broke zero blocks and collect_drops through 8022 found nothing.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
