# resource_live_diamond_drop_11261

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 11381
- updated_step: 11600
- depends_on: goal_mine_diamond_ore, location_diamond_block_11861

## Statement

The former uncollected diamond item from the step-11261 ore break was recovered at step 11444 and no longer remains in the tunnel.

## Evidence

- The iron-pick diamond_ore break fired at 11261, no pickup diamond event followed, and visited.csv shows the 24-tick sweep moved east from x=-3058.70 to -3055.78 rather than west toward the break.
- No pickup diamond exists through 11400; visited.csv shows movement from x=-3058.70 to -3055.78 during the failed 24-tick sweep.
- logs.txt records [INV] diamond +1 and events/events.jsonl records pickup diamond +1 plus the diamond milestone at step 11444.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
