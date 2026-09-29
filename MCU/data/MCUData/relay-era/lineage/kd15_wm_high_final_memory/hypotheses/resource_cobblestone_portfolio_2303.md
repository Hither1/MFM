# resource_cobblestone_portfolio_2303

- kind: resource
- status: active
- confidence: 1.00
- created_step: 2303
- updated_step: 4200
- depends_on: goal_mine_cobblestone, goal_stone_pickaxe, goal_furnace, mechanism_dirt_pillar_return_2325

## Statement

At step 4200 the live inventory has cobblestone x12 and dirt x6 at y57. Reserve eleven cobble for stone pick plus furnace; use the six dirt for the nominal six-level return pillar.

## Evidence

- Step-2303 state held cobblestone x5; pickup cobblestone +1 fired at 2313, no later cobblestone consumption occurred, and step_2400.png shows x6.
- Authoritative step-2430 inventory is cobblestone x6. Events at 2343 and 2372 mined granite, and events at 2401 and 2430 mined andesite; none added cobblestone. The wooden pickaxe retains 40 uses, enough to test six more one-level descent blocks.
- Authoritative step-2575 STATE lists cobblestone x8, dirt x1, granite x4, and andesite x4; the step-2575 stone break has no corresponding pickup yet. Current y49 and the known shaft mouth near y66 imply about seventeen ascent placements, so horizontal mining preserves depth while supplying the missing return reserve.
- Authoritative step-2729 state lists cobblestone x10 and ten decorative blocks. Events show stone breaks at 2618 and 2649 but only one cobblestone pickup at 2657; the verified pillar mechanism raises one level per roughly 14-tick jump-use attempt.
- Cobblestone was x10 at step 2729; use_item cobblestone fired exactly twice at 2915 and 2927, and the current frame shows x8.
- The step-3825 inventory and events verify cobblestone x3 and dirt x4 gained during the successful y67-to-y60 descent; eleven more levels remain to the known y49 bottom.
- Exact visible/current-event totals are cobble 11, dirt 5, diorite 3, andesite 4, granite 4; y49 to the y68 worksite is 19 levels.
- Cobblestone was x3 after step 3787, +1 at 3832, -1 on placement, +1 after the re-mine, then +9 during the step-4174 tunnel; frame 4200 visibly shows cobblestone x12 and dirt x6.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
