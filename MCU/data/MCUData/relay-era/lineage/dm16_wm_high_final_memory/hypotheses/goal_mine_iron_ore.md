# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 2809
- updated_step: 4446
- depends_on: goal_stone_pickaxe, resource_current_lighting_kit, resource_iron_fuel_gate, location_productive_west_stair_6600, location_iron_candidate_7490, resource_surface_wood_after_furnace, resource_stone_pickaxe_secure, location_fresh_iron_strip_5041, location_east_stair_5188, mechanism_manual_front_block_5285, location_fresh_y47_strip_5508, resource_rebuild_stone_pick_7259, location_live_return_shaft_3449, location_y56_west_strip_4800, location_fresh_lower_stair_6000, location_live_iron_floor_6282, location_shallow_coal_2297, location_live_east_branch_3600, goal_furnace, location_corrected_surface_shaft_1727

## Statement

The live mine_iron_ore milestone was environment-verified at step 4446 when the selected stone pickaxe broke the centered tan-speckled block in the y55 east tunnel.

## Evidence

- No current iron event exists; the permanent registry preserves seed-verified iron coordinates.
- No mine_block iron_ore event exists through 3600. The stone pick is selected with about 128 uses, current y is 61, and the candidate is only about 2.6 horizontal blocks from the new column.
- No current iron event exists through step 4800. The player is at y54 with an 81-use stone pick and 35 cobble, 1.6 blocks east of a reset-persistent iron approach.
- events/events.jsonl records both the mine_iron_ore milestone and mine_block iron_ore at step 5166; the turn header reports 6/10 verified.
- No iron event exists through step 600; the registry retains permanent iron sites but all old tunnels were erased.
- No iron event exists through 2400; ore_registry preserves the seed-proven target, about 11.6 horizontal blocks from the current face.
- No mine_block iron_ore event exists through event line 155. Six milestones are verified, the player is at y55 with a 114-use stone pick, and the permanent iron coordinates lie directly east at similar z.
- events/events.jsonl records both MILESTONE mine_iron_ore and mine_block iron_ore at step 4446; the turn header reports 7/10 verified. No pickup followed because authoritative STATE reports zero free inventory slots.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
