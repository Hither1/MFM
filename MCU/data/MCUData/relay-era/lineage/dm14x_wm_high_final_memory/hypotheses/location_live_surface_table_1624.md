# location_live_surface_table_1624

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 1624
- updated_step: 1800
- depends_on: goal_crafting_table

## Statement

The claimed table at (-3001,64,-5564) is stale trajectory contamination and does not exist in the live step-1800 run.

## Evidence

- At step 1624 place_block caused crafting_table -1 at player position (-3000.58,65.25,-5563.70), and the attached frame shows the table top directly under the crosshair.
- Placement removed the table item at step 1624, and look_at its recorded center followed by use_until_gui opened a clean GUI at step 1669 with the player stationary and cursor empty.
- At live step 1624 the player was underground during stair_down; events contain only the original table use at 714/716 and no placement at 1624.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
