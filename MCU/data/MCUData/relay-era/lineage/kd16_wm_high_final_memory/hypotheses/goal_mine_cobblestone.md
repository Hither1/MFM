# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1859
- depends_on: goal_wooden_pickaxe

## Statement

The live reset achieved mine_cobblestone at step 1859 when the deliberately placed north-wall cobblestone block broke under the wooden pickaxe; both the mine_block statistic and milestone are verified.

## Evidence

- Events from steps 3601-3698 show only natural stone breaks and cobblestone pickups; no use_item cobblestone or mine_block cobblestone occurred. The authoritative step-3751 inventory reports cobblestone x13 and the wooden pick has 37 uses left.
- events/events.jsonl records MILESTONE mine_cobblestone, mine_block cobblestone +1, and use_item wooden_pickaxe +1 at step 3800.
- Current milestone list marks it unmet and events contain no mine_block cobblestone.
- events/events.jsonl contains no stone or cobblestone event through step 1200.
- events/events.jsonl records both the mine_cobblestone milestone and mine_block cobblestone at step 2303; the live milestone list reports 4/24 with mine_cobblestone checked.
- Current events contain no mine_block cobblestone and progress remains 1/24.
- events/events.jsonl verifies 13 cobblestone pickups and use_item cobblestone at step 1784 but no mine_block cobblestone; step_1800.png shows the placed cobble under active mining.
- The step-1859 milestone list marks mine_cobblestone complete, and logs.txt/events record mine_block cobblestone +1 at step 1859.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
