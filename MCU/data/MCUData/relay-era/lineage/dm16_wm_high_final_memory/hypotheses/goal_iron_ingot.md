# goal_iron_ingot

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 7522
- updated_step: 5568
- depends_on: goal_mine_iron_ore, goal_furnace, resource_iron_fuel_gate, resource_current_iron_ore, resource_free_ingot_slot_8880, resource_current_lighting_kit, location_live_iron_pocket_4800, location_live_dropped_ingot_5170, location_surface_furnace_6279, location_surface_furnace_3591

## Statement

The live iron_ingot pickup milestone was environment-verified at step 5568 when the dropped furnace-side ingot was recollected.

## Evidence

- Current events through 5400 contain no iron_ingot craft or pickup; two ore are visibly owned.
- No craft_item or pickup iron_ingot exists through step 6000; furnace craft fired at 5997 and iron ore x2 is visible in frame 6000.
- No iron_ingot pickup exists through step 6600; furnace placement is verified at 6279, ore x2 is owned, and a local spruce log block was mined at 6574.
- pickup spruce_log fired at 6712; craft_item spruce_planks +4 and stick +4 fired at 6736/6768; authoritative step-6780 inventory contains iron_ore x2, spruce_planks x2, and stick x4, while furnace placement remains verified at 6279.
- events/events.jsonl records milestone iron_ingot and pickup iron_ingot +1 at step 7129; current STATE lists iron_ingot x1.
- Current events contain no iron ore, ingot craft, or ingot pickup.
- events records craft_item iron_ingot at 5491 but no pickup through 5552; logs record INV +1, then -1 and force-close at the exact furnace interaction pose.
- events/events.jsonl records both MILESTONE iron_ingot and pickup iron_ingot at step 5568; logs.txt records [INV] iron_ingot +1 at the same step.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
