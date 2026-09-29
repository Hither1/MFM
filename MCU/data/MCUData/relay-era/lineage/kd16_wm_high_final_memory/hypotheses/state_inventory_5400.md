# state_inventory_5400

- kind: state
- status: stale
- confidence: 1.00
- created_step: 5400
- updated_step: 6000
- depends_on: goal_stone_pickaxe, goal_furnace, location_west_level_cut_5203, state_inventory_6000, location_current_descent_5400, goal_mine_iron_ore, location_live_east_leg_4824

## Statement

The exact step-5400 inventory snapshot is historical and superseded by the live step-6000 hotbar and 25 later ordinary-rock breaks.

## Evidence

- Superseded by the verified step-7800 snapshot.
- The step-5400 hotbar visibly shows these four stacks; event deltas after the verified step-4800 snapshot add four cobblestone, leave one dirt after the forced drop, and consume 20 stone-pick uses.
- Twenty-three further stone-pick uses and stone/diorite pickups occurred after step 5400.
- Attached hotbar crop gives exact visible stacks; events count 36 stone-pick uses since craft and contain no coal/iron/torch/diamond acquisition through step 5400.
- The authoritative current event stream and final visited segment end at step 4800 with a different inventory and location.
- Magnified step_5400 hotbar gives stack counts; events through 5400 contain no iron-ore pickup or furnace craft, and stone-pick uses reconcile from step 4800.
- Magnified step_5400 hotbar gives the stacks; cobblestone pickups after step 4800 reconcile 32 to 43, granite/diorite pickups reconcile to 4/5, and events count 55 stone-pick uses since craft with no iron-related event.
- Events after 5400 add twenty cobblestone, two granite, and four net diorite pickups and consume 25 stone-pick uses; frame 6000 gives the current stacks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
