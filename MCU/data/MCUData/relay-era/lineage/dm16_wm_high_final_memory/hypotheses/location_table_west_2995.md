# location_table_west_2995

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 2995
- updated_step: 3600
- depends_on: goal_crafting_table, location_current_crafting_table, location_return_wall_2537

## Statement

Refuted as an access route: west-side detours repeatedly collision-stopped and never opened the table; the east loop to (-3007.70,70,-5567.85) opened it at step 3367.

## Evidence

- At step 2995 look_at the stored table centre produced a centered spruce-bark frame and use_until_gui failed, while placement frame 1259 shows the table directly against the trunk with open grass on its west side.
- Steps 3013-3156 record blocked west go_to/use attempts; steps 3324-3367 reached the east pose and GUI open=True.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
