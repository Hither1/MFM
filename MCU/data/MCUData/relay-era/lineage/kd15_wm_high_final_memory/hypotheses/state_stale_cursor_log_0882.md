# state_stale_cursor_log_0882

- kind: mechanism
- status: active
- confidence: 0.95
- created_step: 882
- updated_step: 2069
- depends_on: resource_reset_three_logs, goal_crafting_table, goal_wooden_pickaxe

## Statement

The current GUI cursor label spruce_log x2 is stale: both live logs were consumed by verified spruce-plank crafts at steps 2007 and 2030, the relevant 2x2 grid is empty, and the later stick output was banked at step 2066 while the label remained unchanged. A deliberate force-close should therefore drop no real log stack and permit table placement.

## Evidence

- events/events.jsonl records three spruce-log pickups and three spruce-plank crafts; step 882 reports an empty 2x2 grid and inventory crafting_table x1, spruce_planks x6, stick x4 despite the stale spruce_log x3 cursor label.
- Verified plank crafts consume all three logs; [INV] banked planks x3, sticks x2, and wooden pickaxe x1, and the step-1200 hotbar visibly retains all three stacks with no intervening pickup events.
- events records craft_item crafting_table at step 2607 and craft_item spruce_planks +4 at steps 2667 and 2681; step 2692 inventory is exactly crafting_table x1 and spruce_planks x8 despite CURSOR still naming spruce_log x3.
- events/events.jsonl records two picked-up logs, one spruce-plank craft consuming one log, and the verified table craft consuming those planks. Step 645 lists the remaining log and table in inventory, the attached frame shows both banked in hotbar slots with an empty 2x2 grid, and only the stale aggregate CURSOR label blocks an ordinary close.
- No spruce-log pickup occurred after 443, yet step_1200.png visibly contains the log; therefore the step-648 alleged floor drop did not occur.
- events verify spruce_planks +4 at steps 1293 and 1319; [INV] shows spruce_planks -8 at 1337 and +6 at 1354; the relevant 2x2 row is cells [0,2] out=FULL.
- Current logs end GUI-closed, and current events contain no crafting sequence capable of producing the claimed plank/stick state.
- events/events.jsonl records craft_item spruce_planks +4 at steps 2007 and 2030 and craft_item stick +4 at 2062; logs.txt records [INV] spruce_planks x6 and stick x4, relevant 2x2 grid empty, yet CURSOR still reports spruce_log x2 and guarded close refuses.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
