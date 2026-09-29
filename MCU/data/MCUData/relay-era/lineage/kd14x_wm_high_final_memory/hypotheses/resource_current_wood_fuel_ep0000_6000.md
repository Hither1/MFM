# resource_current_wood_fuel_ep0000_6000

- kind: resource
- status: confirmed
- confidence: 1.00
- created_step: 6000
- updated_step: 7800
- depends_on: goal_iron_ingot, goal_iron_pickaxe, goal_mine_log, goal_furnace

## Statement

The fresh log was fully allocated: two planks produced four sticks and two planks were consumed as fuel to complete all three iron smelts; no wood or fuel remains in inventory or furnace.

## Evidence

- Current events contain no surviving wood/fuel pickup after early crafting, while the standard recipes convert one log to four planks and two fuel planks smelt three items.
- At step 6964 events recorded mine_block spruce_log +1, and at step 6974 both pickup spruce_log +1 and [INV] spruce_log +1 were recorded; authoritative STATE lists spruce_log x1 in hotbar.6.
- events/events.jsonl records craft_item spruce_planks +4 at step 6999; logs.txt records [INV] spruce_planks +4 at step 7002, the relevant 2x2 grid is empty, and the lingering spruce_log cursor label matches the previously verified stale-label mechanism.
- events/events.jsonl records craft_item spruce_planks +4 at step 6999 and craft_item stick +4 at step 7046; logs.txt records inventory spruce_planks +2 at step 7037 and stick +4 at step 7049, while the relevant 2x2 grid is empty.
- craft_item spruce_planks +4 at 6998 and stick +4 at 7045; logs record planks -2 during furnace loading and frame 7200 shows fuel x2 with active flames.
- Craft events prove planks x4 and sticks x4; the furnace was loaded with planks x2, and step 7800 shows empty fuel/input with all three ingots accounted for.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
