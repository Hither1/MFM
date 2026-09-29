# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 2809
- updated_step: 5166
- depends_on: goal_stone_pickaxe, resource_current_lighting_kit, resource_iron_fuel_gate, location_productive_west_stair_6600, location_iron_candidate_7490, resource_surface_wood_after_furnace, resource_stone_pickaxe_secure, location_fresh_iron_strip_5041, location_east_stair_5188, mechanism_manual_front_block_5285, location_fresh_y47_strip_5508, resource_rebuild_stone_pick_7259, location_live_return_shaft_3449, location_y56_west_strip_4800, location_fresh_lower_stair_6000, location_live_iron_floor_6282, location_shallow_coal_2297, location_live_east_branch_3600, goal_furnace

## Statement

Breaking the exposed iron-ore block at the corrected y55 west face satisfied the live mine_iron_ore milestone at step 5166.

## Evidence

- No live iron event through 3600; correct-pick mining removed the furnace obstruction and one stone, while the registered reset-persistent vein remains ~16 east and ~7 north.
- No iron event exists through 4200, but the corrected stone-pick method advanced the axis-aligned tunnel 12 blocks and leaves only about 10.3 horizontal blocks to the persistent registered site; this is a materially changed successful test method.
- The step-4314 state verifies position (-2993.3,55,-5559.7), stone pickaxe selected with 79 uses left, and the preceding ore-watched east tunnel advanced 8.2 blocks without an iron alert. The center block is visually coal ore, so the registered iron remains on the planned north leg.
- events/events.jsonl records both the mine_iron_ore milestone and mine_block iron_ore at step 4587; the authoritative turn header reports 7/10 verified.
- No current iron event exists; the permanent registry preserves seed-verified iron coordinates.
- No mine_block iron_ore event exists through 3600. The stone pick is selected with about 128 uses, current y is 61, and the candidate is only about 2.6 horizontal blocks from the new column.
- No current iron event exists through step 4800. The player is at y54 with an 81-use stone pick and 35 cobble, 1.6 blocks east of a reset-persistent iron approach.
- events/events.jsonl records both the mine_iron_ore milestone and mine_block iron_ore at step 5166; the turn header reports 6/10 verified.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
