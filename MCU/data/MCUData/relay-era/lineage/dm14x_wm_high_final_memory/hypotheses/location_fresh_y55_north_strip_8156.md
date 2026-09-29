# location_fresh_y55_north_strip_8156

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 8156
- updated_step: 9000
- depends_on: resource_rebuild_stone_pick_7259, location_current_vertical_rebuild_shaft_7800, goal_mine_iron_ore, resource_stone_pickaxe_secure, location_y55_crafting_table_8081

## Statement

A verified safe y55 north corridor connects the work alcove near (-2996.7,55,-5564.5) to (-2996.7,55,-5578.7); its exposed blocks through step 8884 were only stone/andesite.

## Evidence

- Current state is at (-2996.7,55,-5564.5); the hazardous cave is northeast at roughly (-2988,-5542), while yaw 180 heads toward decreasing z and away from it. No visited-route evidence marks this y55 direction as searched.
- maps/visited.csv shows movement to (-2996.70,55,-5568.13); events 8182-8395 contain 11 mine_block stone events and no iron event.
- Ground-truth STATE at step 8494 is (-2996.7,55.1,-5569.9); the latest 330-tick strip broke 14 stone, advanced 5.2 blocks, and produced no iron event or ore-watch stop.
- Ground-truth STATE at step 8884 is (-2996.7,55.0,-5578.7). Events 8494-8884 record 16 mined stone/andesite blocks and no iron event or ore-watch stop; the diagnostic reports 8.1 blocks advanced.
- Latest appended maps rows and step-8884 state give the endpoint; strip diagnostics report 14 then 16 breaks with 13.3 blocks net advance and no iron event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
