# resource_unstowed_furnace_5997

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 6000
- updated_step: 6193
- depends_on: goal_furnace, mechanism_gui_cursor_stale_consumed_items

## Statement

The step-5997 furnace output is now securely inventoried in hotbar slot 3; the remaining task is to place it at a reachable surface worksite.

## Evidence

- craft_item furnace fired at 5997 after the grid cleared, but no INV furnace +1 or use_item furnace event follows; current cursor is over hotbar slot 2 and still labels consumed cobble x8.
- At live step 6002 [INV] records furnace +1 and gravel -1, and the current step-6193 STATE explicitly lists furnace x1 in hotbar slot 3. This refutes the earlier claim that the furnace remained unstowed.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
