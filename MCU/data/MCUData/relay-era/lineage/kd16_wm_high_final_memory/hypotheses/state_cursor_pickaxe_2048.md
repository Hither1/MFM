# state_cursor_pickaxe_2048

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 2088
- updated_step: 2096
- depends_on: goal_wooden_pickaxe

## Statement

The wooden pickaxe that was lifted from hotbar slot 3 by the attempted GUI mining action was banked back into inventory at step 2096; it is no longer a cursor hazard.

## Evidence

- The pickaxe was banked with [INV] wooden_pickaxe +1 at step 1962. mine_ahead then ran while GUI open with the pointer over hotbar slot 3 and produced [INV] wooden_pickaxe -1 at step 2048 without a break/use event.
- logs.txt records [INV] wooden_pickaxe +1 immediately after gui_click over hotbar slot 3 at step 2096; the current inventory and frame show the pickaxe in hotbar slot 4.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
