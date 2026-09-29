# goal_iron_ingot

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 6975
- depends_on: goal_mine_iron_ore, goal_furnace, resource_iron_ore_drop_6296

## Statement

The current reset achieved iron_ingot at step 6975 when the deliberately dropped first smelted ingot was recollected beside the underground furnace.

## Evidence

- Events through step 5400 contain neither pickup iron_ore nor pickup iron_ingot.
- The event stream records pickup iron_ore +3 at step 5670 and no pickup iron_ingot through step 5710.
- No pickup iron_ingot event exists through 6600; pickup iron_ore +3 fired at 5670, furnace craft at 6588, and furnace inventory gain at 6594.
- events/events.jsonl has no pickup iron_ingot through step 7200; frame step_7200 shows input x3, fuel x2, active flames, and empty output after about 105 of the expected 200 ticks.
- events/events.jsonl records craft_item iron_ingot +1 at step 7303 but no pickup iron_ingot; step 7307 authoritative state shows iron_ingot x1 in zero-based hotbar slot 7, with furnace input and fuel still occupied.
- events/events.jsonl records MILESTONE iron_ingot and pickup iron_ingot +1 at step 7354; live inventory contains iron_ingot x1.
- The current event stream contains no pickup or smelting-related event.
- events/events.jsonl records craft_item iron_ingot +1 at step 6933, then MILESTONE iron_ingot and pickup iron_ingot +1 at step 6975; live inventory contains iron_ingot x1.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
