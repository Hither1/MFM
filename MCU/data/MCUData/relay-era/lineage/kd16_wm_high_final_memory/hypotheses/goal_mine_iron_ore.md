# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 6623
- depends_on: goal_stone_pickaxe, location_current_east_tunnel_4200, location_seed_north_iron_vein, location_current_iron_approach_3600, state_live_table_recovered_4119, location_live_east_leg_4824, location_live_iron_face_6600, state_live_inventory_reacquired_6600

## Statement

The live reset achieved mine_iron_ore at step 6623 when the north y44 vein face broke under the stone pickaxe; both the environment milestone and mine_block iron_ore statistic are verified.

## Evidence

- No current iron event exists through step 5333. The previous north-facing mine_forward advanced 6.5 blocks without damage and current STATE verifies the remaining geometry and 78-use stone pick.
- Events through 5400 contain no mine_block iron_ore or milestone; current map/frame and use accounting verify the route, equipment, and capacity constraint.
- At step 5706, mine_forward reported 15 blocks broken and 6.0 blocks advanced in 370 ticks, moving from x=-3003.3 to -2997.3 while holding yaw -90; events show only stone/granite/diorite breaks and the stone pick has 63 uses left.
- Final-reset visited rows end at (-2990.30,44,-5575.70); events through 6000 show only stone/granite/diorite breaks and no iron event; ore_registry fixes the approach near (-2985.70,44,-5578.93).
- Live [STATE] at step 6096 gives (-2988.30,44,-5575.70), yaw east, with 47 stone-pick uses. The step 5706-6096 east segment broke 16 stone blocks and advanced about 8.2 blocks without an ore event; the permanent vein remains near (-2985.5,44,-5581.7).
- Events through step 6459 contain no iron break. Steps 6096-6236 advanced due east to x=-2985.30, then steps 6239-6459 advanced due north from z=-5575.70 to -5578.70 while breaking only stone; authoritative STATE reports 32 stone-pick uses and a full hotbar. The permanent ore registry places the reliable approach near (-2985.70,44,-5578.93) and the recess near z=-5581.7.
- Frame 6600 shows iron directly ahead, but ground-truth events and the milestone list contain no current iron break; slot 6 is visibly empty and the stone pick has 27 uses.
- events/events.jsonl records MILESTONE mine_iron_ore and mine_block iron_ore +1 at step 6623.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
