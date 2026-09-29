# mechanism_raw_block_placement

- kind: mechanism
- status: confirmed
- confidence: 0.98
- created_step: 2316
- updated_step: 2527

## Statement

Raw use successfully places a held cobblestone when the player first backs into the adjacent block and targets the exposed side of the east wall; step 2527 verified placement by an inventory decrement from three cobblestone to two.

## Evidence

- At step 2316 place_block emitted a closed-screen gui_right_click note and no use_item event; raw use is the authoritative right-click control.
- Step 2318 raw use produced no use_item event, inventory decrement, or later mine_block cobblestone; place_block had already misrouted at 2316.
- At steps 2318 and 2503 raw use caused no inventory decrement or use_item event while the player was pressed into a one-block-wide shaft; the step-2503 frame shows the crosshair on the close forward wall.
- At step 2515 cobblestone remained x3 and events gained no use_item after raw use from x=-3014.47 while aiming east at the nearby stone wall. The player collision box still intersects the likely destination block x=-3014.
- At step 2527, raw use while at (-3015.69,64.00,-5561.30) and aimed at (-3013.5,64.5,-5561.5) produced [INV] cobblestone -1 after all closer attempts produced no decrement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
