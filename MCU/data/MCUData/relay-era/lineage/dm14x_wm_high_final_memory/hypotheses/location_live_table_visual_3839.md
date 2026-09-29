# location_live_table_visual_3839

- kind: location
- status: confirmed
- confidence: 0.98
- created_step: 3839
- updated_step: 3898
- depends_on: location_current_crafting_table, goal_crafting_table

## Statement

From pose (-3004.49,69,-5566.64), yaw 34 and pitch 45 centers the adjacent crafting table and successfully opens its 3x3 GUI.

## Evidence

- At step 3839, look_at(-3005.5,69.5,-5567.5) followed by use_until_gui failed while the attached frame visibly shows the table clipped at lower left and the crosshair on grass.
- Step-3853 frame visibly shows the table at the left edge while the crosshair rests on dirt; repeated use at pitch +86 changed nothing.
- The step-3853/3878 frame shows the crosshair centered on the dirt pillar while the table side occupies the left edge around pixel (65,166), roughly 255 pixels left and 14 pixels above screen center. Three prior use_until_gui attempts aimed at stale inferred centers produced no GUI.
- The attached step-3892 frame at yaw 54/pitch 45 shows the table centered around pixel x210 versus crosshair x320 at the same vertical level; a roughly 20-degree left correction should center its face.
- At live step 3898, use_until_gui after look_abs(pitch=45,yaw=34) produced GUI open=True with an empty cursor, proving the aim and reach.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
