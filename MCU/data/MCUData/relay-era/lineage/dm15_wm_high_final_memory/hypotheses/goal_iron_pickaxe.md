# goal_iron_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 7522
- updated_step: 11600
- depends_on: goal_iron_ingot, goal_crafting_table, location_iron_candidate_8218, resource_current_iron_ore, resource_iron_fuel_gate, location_current_crafting_table, location_live_iron_pocket_4800, location_return_blocked_by_furnace_6570, location_direct_west_return_tunnel_6654, resource_stone_pickaxe_secure, location_surface_recovery_7749, resource_live_ingots_7129, location_live_return_shaft_3449, location_corrected_iron_face_5126, location_direct_surface_pillar_5356, location_surface_furnace_6279, location_live_table_1813, mechanism_sticks_as_furnace_fuel_10834

## Statement

The iron_pickaxe milestone was environment-verified at step 11323; the physical pick was stowed in zero-based hotbar slot 1 at 11328 and remains selected in frames 11552 and 11600.

## Evidence

- Header remains 8/10 and current events contain no iron-pick craft; frame 9200 proves every non-fuel input and the completed surface return.
- At live step 9800 the score remains 8/10; events contain no iron-pick craft, while frame 9800 still shows ingots x2, ore x1, sticks x4, two empty slots, and the stone pick. Only fresh wood/fuel is absent.
- The live header remains 8/10 and events contain no iron-pick craft; frame 10400 proves ingots x2, ore x1, sticks x4, empty slots, the stone pick, and solved visual alignment on the missing wood source.
- Step 10834 authoritative state shows iron ingot x2, iron ore x1, sticks x4, and a stone pick; the furnace and table coordinates are established this run. Two sticks are sufficient fuel for one smelt, leaving exactly two recipe sticks.
- Frame 11000 proves the final ore is burning, two ingots and two sticks remain, and the verified table recipe costs about 435-650 additional ticks; no iron-pick craft event exists yet.
- At step 11203 STATE reports exactly iron_ingot x3 and stick x2, while the table remains at the verified nearby coordinate and no iron-pick craft event exists yet.
- Current header reports 9/10 and events/events.jsonl records both MILESTONE iron_pickaxe and craft_item iron_pickaxe at step 11323; the cursor is landed over empty hotbar slot 1 for the pending deposit click.
- events/events.jsonl records milestone and craft_item iron_pickaxe at 11323; logs record INV iron_pickaxe +1 at 11328, and later surface frames show it selected.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
