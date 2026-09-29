# mechanism_furnace_hand_break_8799

- kind: mechanism
- status: confirmed
- confidence: 0.98
- created_step: 8799
- updated_step: 9419
- depends_on: goal_furnace

## Statement

A furnace targeted continuously by empty-hand attack breaks after roughly 350-380 adjacent ticks; frame 9419 shows the furnace absent after the uninterrupted 200+180 tick sequence, even though no mine_block furnace statistic was emitted.

## Evidence

- A continuous 200-tick attack from step 8559 to 8759 produced no mine_block furnace event and left the outlined furnace visible at step 8799; the standard no-tool hardness timing predicts roughly 350 ticks.
- Two independent 200-tick attacks (8559-8759 and 8799-8999) produced no mine_block furnace event; each was followed by a pickup sweep, so neither accumulated beyond 200 ticks. The centered furnace remains intact in frame 9039.
- Frames 9039 and earlier show the furnace intact; the adjacent attack entries from 9039 through 9419 total 380 ticks, and frame 9419 shows open air at the former furnace block with dropped item entities ahead.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
