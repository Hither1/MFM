# resource_wood_light_3000

- kind: resource
- status: active
- confidence: 0.98
- created_step: 3000
- updated_step: 3600
- depends_on: goal_mine_iron_ore, goal_iron_ingot, goal_iron_pickaxe, location_surface_tree_3207, goal_stone_pickaxe

## Statement

No wood, sticks, coal, torches, or fuel are held at step 3600. One spruce log is the minimum support resource: four planks can become four sticks from two planks while reserving two plank fuel for three iron ore.

## Evidence

- Step-3000 inventory has only cobble, two picks, and dirt. The current y63 corridor is already becoming dark and ore watching is unreliable without placed light.
- Authoritative step-3574 inventory contains only cobblestone, furnace, stone pickaxe, and wooden pickaxe; the visible nearby spruce supplies the missing log.
- The current hotbar contains only cobblestone and two picks; current events contain no wood pickup after step 1262 and no coal event.
- Current events show the remaining three planks placed at 2218/2224/2235 and sticks dropped at 2253, with no later wood/stick pickup. Frame 3600 shows only the wooden pickaxe.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
