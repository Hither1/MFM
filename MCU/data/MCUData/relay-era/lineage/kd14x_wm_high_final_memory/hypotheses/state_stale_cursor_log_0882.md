# state_stale_cursor_log_0882

- kind: state
- status: active
- confidence: 0.95
- created_step: 882
- updated_step: 1354
- depends_on: resource_reset_three_logs, goal_crafting_table, goal_wooden_pickaxe

## Statement

The survival-GUI cursor parser still reports spruce_log x2 after both logs were event-verified as two four-plank crafts; the authoritative state at step 1354 instead has six planks banked and two planks in 2x2 cells 0 and 2, producing sticks.

## Evidence

- events/events.jsonl records three spruce-log pickups and three spruce-plank crafts; step 882 reports an empty 2x2 grid and inventory crafting_table x1, spruce_planks x6, stick x4 despite the stale spruce_log x3 cursor label.
- Verified plank crafts consume all three logs; [INV] banked planks x3, sticks x2, and wooden pickaxe x1, and the step-1200 hotbar visibly retains all three stacks with no intervening pickup events.
- events records craft_item crafting_table at step 2607 and craft_item spruce_planks +4 at steps 2667 and 2681; step 2692 inventory is exactly crafting_table x1 and spruce_planks x8 despite CURSOR still naming spruce_log x3.
- events/events.jsonl records two picked-up logs, one spruce-plank craft consuming one log, and the verified table craft consuming those planks. Step 645 lists the remaining log and table in inventory, the attached frame shows both banked in hotbar slots with an empty 2x2 grid, and only the stale aggregate CURSOR label blocks an ordinary close.
- No spruce-log pickup occurred after 443, yet step_1200.png visibly contains the log; therefore the step-648 alleged floor drop did not occur.
- events verify spruce_planks +4 at steps 1293 and 1319; [INV] shows spruce_planks -8 at 1337 and +6 at 1354; the relevant 2x2 row is cells [0,2] out=FULL.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
