# location_surface_worksite

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 1200
- updated_step: 1200
- depends_on: goal_crafting_table

## Statement

Refuted in its prior form: the player did not remain beside a table through step 1200 and is not at (-3004.20,67,-5566.53); by step 1200 the live pose is (-3003.70,56,-5564.30).

## Evidence

- Player remained stationary from placement through step 1200; step-1103 frame centers the placed table and use_until_gui opened it from that pose.
- Step 1485 ground-truth state gives the new player position, and pickup crafting_table was verified at step 1471.
- Ground-truth position and stair_down report at step 1776; pickups of the table and spare log were verified at steps 1471 and 1473.
- Map coordinates prove decreasing x along yaw 89, so prior east/south labels were reversed. Table/log pickups are event-verified at 1471/1473; step 1800 remains at the endpoint with yaw 179.
- Table mine/pickup verified at 1440/1471; current hotbar shows the table, planks, and log.
- Both table recoveries are event-verified (1471 and 2903), and map coverage shows the old worksite only connects back along the trench.
- use_item crafting_table occurred at 961 with no later table mine/pickup; visited.csv fixes the step-1200 player position.
- The final current-run visited row fixes y56, and events record eight stone breaks during the descent after leaving the step-711 table.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
