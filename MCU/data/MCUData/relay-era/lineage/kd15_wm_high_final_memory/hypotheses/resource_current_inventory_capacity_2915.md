# resource_current_inventory_capacity_2915

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 2915
- updated_step: 3600
- depends_on: goal_wooden_pickaxe, goal_mine_cobblestone, mechanism_dirt_pillar_return_2325, state_inventory_3600

## Statement

The claim that live step 3600 holds cobblestone x2 and six free hotbar slots belongs to another trajectory and is false for this reset; the current compact inventory has only the wooden pickaxe and two free stack slots.

## Evidence

- Authoritative step-2915 state lists all three stacks unchanged and Held: wooden_pickaxe; actions 190-192 called place_block without first equipping the plank stack.
- Authoritative step-3083 state reports 0 slots free and the four named stacks. Events at 3018, 3042, and 3063 plus pickups through 3082 verify the dirt x3; the confirmed pillar mechanism shows look-down jump+use consumes dirt safely.
- Authoritative step-3462 STATE lists 0 slots free and cobblestone x6; events verify four cobblestone pickups during the preceding mine_forward despite zero free slots. Dirt jump-pillar placement already consumed three dirt at steps 3125-3127, so it is a proven way to free a slot later.
- Step-3600 frame and events verify current stacks; the step-3125 pillar consumed three dirt at about one level per block, while recipes require 3+8 cobble.
- step_3600 hotbar shows three occupied slots and six empty; the furnace recipe requires eight cobblestone and no current furnace event exists.
- Current events contain no stone break or cobblestone pickup, the milestone remains unmet, and the current step-3600 frame shows only the wooden pickaxe.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
