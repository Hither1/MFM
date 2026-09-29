# mechanism_jump_place_shaft_2872

- kind: mechanism
- status: confirmed
- confidence: 0.99
- created_step: 2872
- updated_step: 2879
- depends_on: resource_current_cobblestone, location_fresh_direct_descent_2530, mechanism_raw_block_placement

## Statement

Four jump ticks followed by one raw use while holding cobblestone successfully place exactly one cobblestone in the one-block shaft above the protected floor block.

## Evidence

- The player stands at y56 with pitch 80 on the floor block; four jump ticks should lift the collision box above the y56 destination cell before the single use tick.
- At step 2879 STATE rose from y56.00 to y57.25, [INV] recorded cobblestone -1, and the attached view shows the placed cobblestone centered directly below; no floor-block mine event occurred.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
