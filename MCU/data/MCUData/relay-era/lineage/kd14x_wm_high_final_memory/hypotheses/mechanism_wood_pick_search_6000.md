# mechanism_wood_pick_search_6000

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 6000
- updated_step: 7200
- depends_on: goal_mine_iron_ore, state_inventory_6000

## Statement

Wooden-pick exposure successfully reserved all 38 remaining stone-pick uses, but the wooden pick is now exhausted and broke at step 7075; all further mining must use slot 3.

## Evidence

- Wooden-pick cobblestone mining is verified earlier; capacities leave 30 wooden versus 39 stone uses, and iron requires stone tier.
- Events 6066-6587 record wooden-pick use on diorite, stone, and andesite only; stone use remains 93 total.
- Events from 6066 through 7075 record ordinary blocks mined with the wooden pick and its break_item event; no later stone-pick use occurred.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
