# mechanism_wood_pick_search_6000

- kind: mechanism
- status: stale
- confidence: 1.00
- created_step: 6000
- updated_step: 6000
- depends_on: goal_mine_iron_ore, state_inventory_6000, goal_iron_ingot

## Statement

The claim that the wooden pick broke after step 6000 belongs to a different trajectory; in the live step-6000 state it still has 26 uses and is reserved as one-smelt furnace fuel.

## Evidence

- Wooden-pick cobblestone mining is verified earlier; capacities leave 30 wooden versus 39 stone uses, and iron requires stone tier.
- Events 6066-6587 record wooden-pick use on diorite, stone, and andesite only; stone use remains 93 total.
- Events from 6066 through 7075 record ordinary blocks mined with the wooden pick and its break_item event; no later stone-pick use occurred.
- Current events end at step 6000 with 33 wooden-pick uses and no break_item wooden_pickaxe event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
