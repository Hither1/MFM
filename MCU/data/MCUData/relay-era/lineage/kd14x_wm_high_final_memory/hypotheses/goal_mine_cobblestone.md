# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2303
- depends_on: goal_wooden_pickaxe

## Statement

The current reset achieved mine_cobblestone at step 2303 when the deliberately placed north-wall cobblestone block was mined with the wooden pickaxe.

## Evidence

- events/events.jsonl records MILESTONE mine_cobblestone and mine_block cobblestone at step 1986; the authoritative state reports cobblestone x3.
- No cobblestone mine event or milestone exists in the current event file.
- events/events.jsonl records nine cobblestone pickups and no mine_block cobblestone or milestone through step 3600; step_3600.png shows cobblestone x9 selected.
- Events from steps 3601-3698 show only natural stone breaks and cobblestone pickups; no use_item cobblestone or mine_block cobblestone occurred. The authoritative step-3751 inventory reports cobblestone x13 and the wooden pick has 37 uses left.
- events/events.jsonl records MILESTONE mine_cobblestone, mine_block cobblestone +1, and use_item wooden_pickaxe +1 at step 3800.
- Current milestone list marks it unmet and events contain no mine_block cobblestone.
- events/events.jsonl contains no stone or cobblestone event through step 1200.
- events/events.jsonl records both the mine_cobblestone milestone and mine_block cobblestone at step 2303; the live milestone list reports 4/24 with mine_cobblestone checked.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
