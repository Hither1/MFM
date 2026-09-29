# goal_iron_ingot

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 7522
- updated_step: 5211
- depends_on: goal_mine_iron_ore, goal_furnace, resource_iron_fuel_gate, resource_current_iron_ore, resource_free_ingot_slot_8880, resource_current_lighting_kit, location_live_iron_pocket_4800, location_live_dropped_ingot_5170

## Statement

The iron_ingot pickup milestone was environment-verified at live step 5211 after the furnace-side dropped ingot was recollected into the freed inventory slot.

## Evidence

- The final south-branch search broke only stone at 10942/10962. STATE contains only cobblestone, sticks, and the one-use stone pickaxe; no pickup iron_ingot event exists.
- No pickup iron_ingot exists. All three secured ore were converted by craft_item iron_ingot at 8336/8780; repeated free-capacity sweeps found no old output, and final strips through 10962 found only stone.
- events has no pickup iron_ingot through 11600; the last pick broke at 11319, current GUI resources are only cobblestone/sticks, and smelting/output pickup alone costs most of the remaining budget.
- The previous final-400 infeasibility statement is invalid after reset; current budget and persistent ore sites reopen the chain.
- Current events contain no iron_ingot craft or pickup through 2400; furnace is secured and the remaining horizon is 9600 ticks.
- No ingot event through 3000; furnace is owned and live coal now satisfies the fuel gate with 9000 ticks remaining.
- Two ore pickups and two coal are verified through 4800; furnace use_item at 4630 verifies placement, while no iron-ingot pickup exists.
- events/events.jsonl records the iron_ingot milestone and pickup iron_ingot +1 at step 5211; authoritative STATE reports iron_ingot x1 in hotbar slot 8.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
