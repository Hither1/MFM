# mechanism_narrow_bore_drop_access_5400

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 5400
- updated_step: 5710
- depends_on: resource_current_iron_drop_5062

## Statement

When mine_ahead leaves an unwalkable narrow bore, mine_forward can open the foot-and-eye corridor and carry the player through trapped drop sites for collection.

## Evidence

- Steps 5194-5334 broke one iron and three stone with mine_ahead, but the next 20 forward ticks moved 0.01 blocks while backward moved 4.06.
- The step-5494 mine_forward advanced about 3.8 blocks through the prior bore and produced pickup iron_ore +3 at step 5670.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
