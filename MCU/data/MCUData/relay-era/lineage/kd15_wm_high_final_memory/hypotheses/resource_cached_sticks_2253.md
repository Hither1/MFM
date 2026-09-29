# resource_cached_sticks_2253

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 2400
- updated_step: 4800
- depends_on: goal_stone_pickaxe

## Statement

The old step-2253 stick cache was recovered at 4587 and consumed by the stone-pick recipe; this source cache is exhausted. Two sticks now exist only in the new step-4768 GUI-drop cache.

## Evidence

- Logs records stick -2 at 2250 followed by a deliberate force-close/drop at the unchanged pose at step 2253.
- Logs prove stick -2 and forced drop at 2253; events contain no later stick pickup, while the player has moved roughly six blocks away.
- Logs record stick -2 at step 2250 and forced drop at the unchanged pose at 2253; events contain no later stick pickup. Only 1,947 environment ticks have elapsed.
- Authoritative events/events.jsonl records pickup stick +2 at step 4587, and the live inventory reports stick x2 in hotbar slot 5.
- pickup stick +2 fired at 4587, the stone-pick craft consumed its grid ingredients at 4693, and forced close reported stickx2 dropped at 4768.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
