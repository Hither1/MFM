# goal_mine_cobblestone

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 2085
- depends_on: goal_wooden_pickaxe, resource_wooden_pickaxe_secure, mechanism_raw_block_placement

## Statement

Breaking the deliberately placed cobblestone in the live y56 shaft satisfied the mine_cobblestone milestone at step 2085.

## Evidence

- No current mine_block cobblestone event exists.
- Current events through step 2395 contain no mine_block stone, cobblestone pickup, mine_block cobblestone, or milestone; frame 2400 shows only sticks, planks, wooden pick, and dirt.
- events/events.jsonl and the live harness report MILESTONE mine_cobblestone plus mine_block cobblestone at step 2917.
- No stone/cobblestone mine or pickup event exists in the current prefix through step 600.
- events contain stone breaks at 1765/1794 and cobblestone pickup at 1775, but no mine_block cobblestone or milestone through step 1800; frame 1800 shows cobble x1.
- At step 1997 STATE reports cobblestone x8 at (-3008.3,56,-5561.7); the completed dig_down broke another stone at step 1997. The proven narrow-shaft placement procedure requires an empty adjacent cell and a solid wall two blocks ahead, which this plan creates eastward.
- At step 2049 raw use caused [INV] cobblestone -1 with GUI closed; the camera has not moved since the placement action.
- events/events.jsonl records both the mine_cobblestone milestone and mine_block cobblestone at step 2085; the harness reports 4/10 verified.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
