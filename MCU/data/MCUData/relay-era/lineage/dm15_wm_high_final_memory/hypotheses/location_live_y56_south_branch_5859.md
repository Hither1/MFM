# location_live_y56_south_branch_5859

- kind: location
- status: refuted
- confidence: 0.95
- created_step: 5859
- updated_step: 6000
- depends_on: location_y56_west_strip_4800, resource_current_lighting_kit, resource_stone_pickaxe_secure

## Statement

The south endpoint pocket is non-traversable and retired: four stone breaks advanced only 0.4 block, then a 24-tick forward-jump produced no movement.

## Evidence

- Current STATE is at the east corridor endpoint with yaw 180 and 73 stone-pick uses remaining. The north entrance repeatedly failed to advance, while the opposite south wall has not yet been mined on this live trajectory.
- At step 5966 STATE is (-2991.72,56.00,-5566.30), yaw 0, stone pick 69 uses. Events verify four stone blocks mined in the south face since step 5859 and no iron; the live frame shows a lit two-high stone passage with a flat-looking floor and dropped cobblestone ahead.
- STATE remained (-2991.72,56,-5566.30) at steps 5966-6000; strip diagnostic stopped for zero advance and the subsequent jump moved 0.00.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
