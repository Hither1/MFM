# mechanism_wrong_held_item_3530

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 3600
- updated_step: 3600
- depends_on: resource_stone_pickaxe_secure, resource_current_lighting_kit

## Statement

Mining procedures do not automatically equip a pickaxe: with torch selected, stair_down and mine_forward broke zero blocks; explicit stone-pick selection restored block breaking.

## Evidence

- Step 3410 stair_down and step 3530 mine_forward report zero breaks while torch was held; after equip at 3532, furnace and stone broke at 3565/3585.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
