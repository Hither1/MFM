# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2917
- depends_on: goal_wooden_pickaxe, resource_wooden_pickaxe_secure, mechanism_raw_block_placement

## Statement

Breaking the deliberately placed cobblestone in the live shaft satisfied the mine_cobblestone milestone at step 2917.

## Evidence

- No milestone or mine_block cobblestone event exists through step 1200; events instead show eight natural stone breaks and seven cobblestone pickups.
- No current-run mine_block cobblestone or milestone exists through step 1223; eight cobblestone are owned, and procedures/place_cobblestone_in_narrow_shaft.md records the clearance-dependent placement method.
- No current-run mine_block cobblestone or milestone event exists through step 1365. The player holds twelve cobblestone, and the proven narrow-shaft procedure requires an empty adjacent cell backed by a solid wall plus clearance from the player collision box.
- At step 1420, immediately after raw use while facing east at pitch 0, [INV] reports cobblestone -1 (12 to 11), proving a block was placed in the targeted opening. The next action can therefore mine the same crosshair target.
- events/events.jsonl records MILESTONE mine_cobblestone and mine_block cobblestone at step 1456; authoritative progress is now 4/10.
- No current mine_block cobblestone event exists.
- Current events through step 2395 contain no mine_block stone, cobblestone pickup, mine_block cobblestone, or milestone; frame 2400 shows only sticks, planks, wooden pick, and dirt.
- events/events.jsonl and the live harness report MILESTONE mine_cobblestone plus mine_block cobblestone at step 2917.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
