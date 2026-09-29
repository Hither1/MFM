# goal_iron_pickaxe

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 7522
- updated_step: 10800
- depends_on: goal_iron_ingot, goal_crafting_table, location_iron_candidate_8218, resource_current_iron_ore, resource_iron_fuel_gate, location_current_crafting_table, location_live_iron_pocket_4800, location_return_blocked_by_furnace_6570, location_direct_west_return_tunnel_6654, resource_stone_pickaxe_secure, location_surface_recovery_7749

## Statement

The iron_pickaxe milestone remains verified from step 8008, but the physical pick was lost with all inventory in the step-10624 lava death.

## Evidence

- Events verify ingot crafts at 5160/5419/6107; frame 7800 shows ingots x3 and sticks x2, and no craft_item iron_pickaxe exists through 7800.
- At step 8008 events/events.jsonl and the harness report MILESTONE iron_pickaxe plus craft_item iron_pickaxe +1; GUI remains open with the cursor landed over hotbar slot 0, and the planned final deposit click did not execute before the milestone return.
- events/events.jsonl records milestone and craft_item iron_pickaxe at 8008, logs records [INV] iron_pickaxe +1 at 8013, and eleven later use_item iron_pickaxe events leave 239/250 uses.
- Milestone and craft_item iron_pickaxe fire at 8008; inventory deposit is logged at 8013; 51 subsequent use_item iron_pickaxe events through 8993 leave 199 uses.
- events records milestone/craft_item iron_pickaxe at 8008 and exactly 80 later use_item iron_pickaxe events through step 9598; frame 9600 shows it selected.
- craft_item iron_pickaxe and its milestone fired at step 8008; exactly 105 subsequent use_item iron_pickaxe events leave 145 uses.
- Current STATE explicitly reports Held: iron_pickaxe (142/250 uses left), and the iron_pickaxe milestone remains environment-verified.
- events verifies craft_item/milestone iron_pickaxe at 8008; step-10624 INV removes iron_pickaxe x1 and respawns empty.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
