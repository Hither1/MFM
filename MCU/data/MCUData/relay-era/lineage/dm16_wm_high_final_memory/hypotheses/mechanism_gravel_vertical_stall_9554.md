# mechanism_gravel_vertical_stall_9554

- kind: mechanism
- status: stale
- confidence: 1.00
- created_step: 9554
- updated_step: 10800
- depends_on: location_diamond_block_11861

## Statement

The gravel-stall condition is historical and stale for the current face: west mining from x=-3031.77 to -3045.57 stayed at y12 and produced only coal/stone events, with no gravel after step 10157.

## Evidence

- Steps 9386-9554 advanced west from x=-3020.7 to -3022.7 while five gravel pickups occurred; the final pose rose to y12.74 and mine_forward reported a two-cycle movement stall after six breaks.
- Steps 9386-9554 collected five gravel and raised the player to y13.20 before a two-cycle stall; dig_down reached y11 at step 9580, while the step-9600 map position is still unchanged after one diorite break.
- Authoritative step-9665 STATE is (-3024.55,11.74,-5557.31); the procedure note reports four blocks broken, 1.7 advanced, and a two-cycle no-movement stall, while INV gained gravel x1.
- The step-9789 mine_forward note reports three blocks broken and 0.9 advanced; events 9714/9746/9781 are all gravel, and STATE moved from (-3024.70,11,-5557.31) to (-3024.70,12,-5558.48).
- STATE moved from (-3029.70,11.00,-5558.48) at step 10076 to (-3031.15,13.02,-5558.48) at 10157; mine_forward reported four breaks, 1.2 advanced, and a two-cycle stall.
- Events 10218-10792 contain only coal_ore/stone mining on the west line; maps hold y at 12.00-12.20 while x decreases 13.8 blocks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
