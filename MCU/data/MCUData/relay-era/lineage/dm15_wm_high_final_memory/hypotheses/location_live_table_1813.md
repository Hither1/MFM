# location_live_table_1813

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2132
- updated_step: 2181
- depends_on: goal_crafting_table

## Statement

The crafting table placed beside (-2999.08,64.00,-5563.33) remains reachable and its GUI can be reopened from the stored pose with pitch 8, yaw -114.

## Evidence

- Current-prefix events verify crafting_table placement/use at steps 1816/1820, no later mine_block or pickup event exists, and the player successfully left the area after closing the GUI.
- At live step 2181, go_to returned to (-2998.64,64.00,-5563.26), look_abs restored pitch 8/yaw -114, and use_until_gui successfully opened the crafting-table screen.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
