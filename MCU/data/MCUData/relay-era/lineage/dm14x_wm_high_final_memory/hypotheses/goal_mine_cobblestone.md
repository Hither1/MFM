# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 1456
- depends_on: goal_wooden_pickaxe, resource_wooden_pickaxe_secure, mechanism_raw_block_placement

## Statement

Breaking the precisely placed cobblestone in the east-wall opening satisfied the mine_cobblestone milestone at live step 1456.

## Evidence

- Milestone ledger remains 3/24 at step 1500; pickup cobblestone occurred at 1479, enabling the required placed-block test.
- The live ledger advanced to 4/24 and events/events.jsonl records both MILESTONE mine_cobblestone and mine_block cobblestone at step 1652.
- No current cobblestone mine event exists; milestone semantics require breaking cobblestone rather than natural stone.
- No milestone or mine_block cobblestone event exists through step 1200; events instead show eight natural stone breaks and seven cobblestone pickups.
- No current-run mine_block cobblestone or milestone exists through step 1223; eight cobblestone are owned, and procedures/place_cobblestone_in_narrow_shaft.md records the clearance-dependent placement method.
- No current-run mine_block cobblestone or milestone event exists through step 1365. The player holds twelve cobblestone, and the proven narrow-shaft procedure requires an empty adjacent cell backed by a solid wall plus clearance from the player collision box.
- At step 1420, immediately after raw use while facing east at pitch 0, [INV] reports cobblestone -1 (12 to 11), proving a block was placed in the targeted opening. The next action can therefore mine the same crosshair target.
- events/events.jsonl records MILESTONE mine_cobblestone and mine_block cobblestone at step 1456; authoritative progress is now 4/10.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
