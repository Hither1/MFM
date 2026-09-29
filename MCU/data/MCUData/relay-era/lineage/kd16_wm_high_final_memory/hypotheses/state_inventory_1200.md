# state_inventory_1200

- kind: state
- status: stale
- confidence: 1.00
- created_step: 1200
- updated_step: 1200
- depends_on: goal_wooden_pickaxe, state_stale_cursor_log_0882, goal_mine_log, resource_reset_three_logs, goal_crafting_table

## Statement

This ID described an older trajectory's step-1200 snapshot; retire it as stale because the live reset has now independently reached step 1200.

## Evidence

- Step-1200 frame shows the three hotbar stacks; prior [INV] deltas are planks +3 at 954, sticks +2 at 976, wooden_pickaxe +1 at 990; events have no later resource changes.
- pickup spruce_log +1 fired at step 914, no later inventory-changing event exists, and step_1200.png shows the single log stack in slot 0.
- A new authoritative step-1800 state supersedes this timestamped snapshot.
- Direct inspection of step_1200.png agrees with the current run's craft and inventory deltas.
- Current event stream ends at step 375 and the latest frame/map state is step 600 with one log only.
- The latest-reset maps segment and current events identify a different live step-1200 state; use state_current_pick_recipe_1200 instead.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
