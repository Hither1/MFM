# resource_wood_light_3000

- kind: resource
- status: active
- confidence: 0.98
- created_step: 3000
- updated_step: 4258
- depends_on: goal_mine_iron_ore, goal_iron_ingot, goal_iron_pickaxe, location_surface_tree_3207, location_live_spruce_target_4200, goal_mine_log

## Statement

The live reset now has seven banked spruce planks: the extra log was consumed by the verified four-plank craft at step 4250, the output was banked into hotbar slot 0, and the relevant 2x2 grid is empty. Two planks can later make four sticks while at least two more fuel three iron smelts.

## Evidence

- Authoritative step-3574 inventory contains only cobblestone, furnace, stone pickaxe, and wooden pickaxe; the visible nearby spruce supplies the missing log.
- The current hotbar contains only cobblestone and two picks; current events contain no wood pickup after step 1262 and no coal event.
- Authoritative live inventory at step 3569 lists spruce_planks x3 and no sticks/logs/coal; two planks are required for four sticks and two plank fuel smelts three ore. The attached frame places the player in the surface spruce canopy with trunks and leaves nearby.
- The current hotbar frame and event accounting verify three planks and no other wood/fuel; spruce trunks are visible around the current pose.
- Frame 4200 shows planks x3 and the targeted log; events through 4200 contain no later wood, stick, coal, or iron gain.
- Ground-truth events record mine_block spruce_log at step 4211 and pickup spruce_log at step 4221; authoritative STATE lists spruce_log x1 and spruce_planks x3.
- events/events.jsonl records mine_block spruce_log at step 4211 and pickup spruce_log at step 4221; step 4235 records spruce_log -1 as the stack is lifted from hotbar slot 7, and [CURSOR] confirms spruce_log x1 off-inventory in the open survival inventory.
- events/events.jsonl records craft_item spruce_planks +4 at step 4250; logs record spruce_planks +4 at step 4255; authoritative step-4258 inventory reports spruce_planks x7 and the open survival inventory has no occupied 2x2 cells. The lingering spruce_log cursor label is stale and fully accounted for.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
