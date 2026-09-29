# mechanism_hand_search_10266

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 10266
- updated_step: 10800
- depends_on: goal_mine_iron_ore

## Statement

Bare-handed strip mining cannot productively break ordinary stone in this budget and must not be retried.

## Evidence

- Minecraft attack can break stone without a held tool, while use_item statistics show each pick-mined block consumes one of the six remaining uses; this turn tests whether strip_mine can still advance bare-handed.
- At step 10428, empty-hand strip_mine reported broke 0 blocks and advanced 0.7 blocks before stopping on the visible plain-stone face; no stat or inventory event changed after step 10257.
- Step-10428 strip_mine entered only an existing gap, broke zero blocks, and stalled for 158 ticks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
