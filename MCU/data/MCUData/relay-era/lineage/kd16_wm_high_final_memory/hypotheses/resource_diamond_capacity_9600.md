# resource_diamond_capacity_9600

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 9600
- updated_step: 10800
- depends_on: goal_mine_diamond_ore

## Statement

The earlier dropped-stack capacity narrative belongs to another trajectory and is stale; current capacity is instead proven by the stone-pick break at step 10544.

## Evidence

- The step-9900 inventory has zero free slots and includes a singleton wooden pickaxe. The prior dirt drop was re-collected because the avatar stayed near it, whereas the productive cardinal tunnel now permits immediate one-way separation.
- logs steps 9909-9953 show wooden_pickaxe -1, forced drop, then pickup wooden_pickaxe +1 during two blocks of southward advancement; live inventory at 10027 has zero free slots.
- Live step 10151 reports zero free slots, dirt x16, cobblestone x79, no wooden pickaxe, and cobblestone +4 during the last 100-tick advance. The prior force-drop removed the wooden pick, but ordinary cobblestone then occupied its slot; dropping a whole dirt stack and changing branch direction tests durable separation.
- Inventory lost dirt x16 at 10160 and no later dirt pickup exists. Maps show retreat to z=-5571.11, while events verify pickup wooden_pickaxe +1 at 10189; the latest frame shows every hotbar slot occupied.
- Logs record iron_ore x2 moved into hotbar slot 3, use_item iron_ore at 10691/10695, and the final iron_ore -1 delta at 10697; no later inventory item fills that slot.
- Step 11093 reports zero free slots, cobblestone x82, and nine occupied hotbar stacks when the split cobblestone stack is included; no diamond pickup exists. The stone pickaxe is verified in hotbar slot 9 and is expendable now that the iron pick remains usable.
- Inventory deltas stone_pickaxe -1 at 11102 and andesite -8 at 11292, followed by force-closes and separation travel; no subsequent inventory pickup refilled both slots.
- Current events/maps do not contain the cited remote andesite/iron-ore disposal sequence. Frame 10800 directly verifies one empty slot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
