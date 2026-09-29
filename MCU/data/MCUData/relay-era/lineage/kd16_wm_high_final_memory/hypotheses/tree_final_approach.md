# tree_final_approach

- kind: mechanism
- status: confirmed
- confidence: 0.99
- created_step: 399
- updated_step: 1800
- depends_on: tree_ahead_start

## Statement

A reachable, centred spruce log takes about 70 stationary hand-attack ticks to break; a 75-tick no-break stop indicates miss or lack of reach and must trigger a position/aim change.

## Evidence

- At step 399 the spruce fills the center view, but the preceding centered advance gained only 1.92 blocks and the chop still diagnosed out-of-reach.
- The step 551 frame shows a full-height bark face occupying the right quarter of the view, while movement reached (-3006.9,69.0,-5566.4), substantially closer than the failed step 399 chop.
- Current frame visibly shows bark filling the centre/right and the attack arm against it; state remains (-3007.13,69.00,-5566.30). No event yet proves a break.
- Direct chops produced spruce_log mine events at steps 622 and 698; failed attempts were misses or out of reach, not a failure of hand chopping.
- Current-run mine_block spruce_log events occurred at steps 101 and 563; the action containing the latter began at 493 and the player stayed adjacent.
- Four current chops timed out after 75 ticks and the only verified break was spruce leaves at step 580; alleged log events at steps 101 and 563 are absent from the current event file.
- aim_at_tree centred bark at step 807 and chop_tree produced mine_block spruce_log plus the milestone at step 877.
- The centred approach at steps 807-877 produced mine_block spruce_log after about 70 ticks; multiple unchanged rays later guard-stopped at 75 with no event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
