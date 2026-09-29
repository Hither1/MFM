# tree_close_reach

- kind: mechanism
- status: confirmed
- confidence: 0.90
- created_step: 286
- updated_step: 600
- depends_on: tree_ahead_start

## Statement

On uneven canopy terrain, a nominal 2-3 block centred approach does not guarantee trunk reach; verify by the break event or move closer after a 75-tick miss.

## Evidence

- Two correctly centred chops broke nothing and explicitly diagnosed out-of-reach; the current frame still shows the trunk through nearby leaves.
- After a 2.26-block raw approach and a further 1.92-block centred travel, chop_tree still timed out for 75 ticks with no event.
- Four centred chop attempts ended after 75 ticks with no block break, while the closer step-493 attempt broke spruce at step 563.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
