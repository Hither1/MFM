# resource_live_cobblestone_1574

- kind: resource
- status: active
- confidence: 1.00
- created_step: 1574
- updated_step: 2400
- depends_on: goal_wooden_pickaxe, goal_mine_cobblestone, location_current_shaft_1800, state_live_ascent_pillar_2239

## Statement

At step 2400 the live cobblestone stack is x26; at least 11 must remain reserved for the stone pickaxe and furnace while the other 15 can fund ascent.

## Evidence

- Authoritative step-1574 state reports cobblestone x6 and wooden pickaxe 50/59; events record six consecutive stone breaks and six cobblestone pickups from steps 1419-1574, while visited.csv shows a controlled vertical descent to y57.
- Event totals are pickup cobblestone +13 and use_item cobblestone +1; the step-1800 frame visibly shows cobblestone x12, dirt x3, sticks x2, planks x3, and the wooden pick.
- Authoritative step-1859 state lists cobblestone x12, the frame shows fresh break particles/items at the face, and mine_block cobblestone fired at this step without a corresponding pickup yet.
- Net event accounting is 27 cobblestone pickups minus one placement, with no later cobble use; the frame shows x26.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
