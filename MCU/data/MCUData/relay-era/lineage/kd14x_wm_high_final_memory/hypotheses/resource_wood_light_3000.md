# resource_wood_light_3000

- kind: resource
- status: active
- confidence: 0.95
- created_step: 3000
- updated_step: 3600
- depends_on: goal_mine_iron_ore, goal_iron_ingot, goal_iron_pickaxe, location_surface_tree_3207

## Statement

At step 3600 no wood, sticks, coal, torches, or fuel are held. One spruce log is the minimum post-furnace support target because four planks can supply four sticks and two plank fuel for three iron ore.

## Evidence

- Step-3000 inventory has only cobble, two picks, and dirt. The current y63 corridor is already becoming dark and ore watching is unreliable without placed light.
- Authoritative step-3574 inventory contains only cobblestone, furnace, stone pickaxe, and wooden pickaxe; the visible nearby spruce supplies the missing log.
- The current hotbar contains only cobblestone and two picks; current events contain no wood pickup after step 1262 and no coal event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
