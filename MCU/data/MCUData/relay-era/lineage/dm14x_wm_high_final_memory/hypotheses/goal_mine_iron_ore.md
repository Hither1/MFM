# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 2809
- updated_step: 4587
- depends_on: goal_stone_pickaxe, resource_current_lighting_kit, resource_iron_fuel_gate, location_productive_west_stair_6600, location_iron_candidate_7490, resource_surface_wood_after_furnace, resource_stone_pickaxe_secure, location_fresh_iron_strip_5041, location_east_stair_5188, mechanism_manual_front_block_5285, location_fresh_y47_strip_5508, resource_rebuild_stone_pick_7259, location_live_return_shaft_3449, location_y56_west_strip_4800, location_fresh_lower_stair_6000, location_live_iron_floor_6282, location_shallow_coal_2297, location_live_east_branch_3600

## Statement

Breaking the iron-ore block exposed at the end of the fresh y55 north branch satisfied the mine_iron_ore milestone at live step 4587.

## Evidence

- No mine_block iron event exists through 2400; stone_pickaxe is securely owned and permanent registry records iron near (-2992.7,55,-5566.4) and (-2988.3,55,-5566.7).
- No live iron event through 3000; current pose, tool, coal, planks, and permanent iron coordinates make the direct lit route feasible without first recovering the table.
- mine_forward at yaw 247 broke four stone blocks in steps 3191-3260 but advanced only 0.2 horizontal blocks and ended at y56.02; the runner diagnosed a blocked passage. The registered target remains about 15.6 blocks east and 6.7 blocks north.
- Authoritative step-3530 state says Held: torch and hotbar.6=stone_pickaxe; both the 3410 stair_down and 3530 mine_forward broke zero blocks. The prior diagonal call at 3269 did break four stone blocks while the stone pick was active, proving the surrounding face is mineable.
- No live iron event through 3600; correct-pick mining removed the furnace obstruction and one stone, while the registered reset-persistent vein remains ~16 east and ~7 north.
- No iron event exists through 4200, but the corrected stone-pick method advanced the axis-aligned tunnel 12 blocks and leaves only about 10.3 horizontal blocks to the persistent registered site; this is a materially changed successful test method.
- The step-4314 state verifies position (-2993.3,55,-5559.7), stone pickaxe selected with 79 uses left, and the preceding ore-watched east tunnel advanced 8.2 blocks without an iron alert. The center block is visually coal ore, so the registered iron remains on the planned north leg.
- events/events.jsonl records both the mine_iron_ore milestone and mine_block iron_ore at step 4587; the authoritative turn header reports 7/10 verified.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
