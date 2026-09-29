# resource_light_fuel_6000

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 6000
- updated_step: 6000
- depends_on: state_inventory_6000, goal_mine_iron_ore, goal_iron_ingot, state_inventory_7200, mechanism_torch_recipe_5707, state_inventory_9600, state_inventory_6600

## Statement

The prior claim that three planks are held at live step 6000 is false for this trajectory.

## Evidence

- Torch use events at 7073 and 7737 after four were crafted; step-7800 hotbar shows coal x2 and torches x2.
- Step-9600 hotbar zoom shows coal x2 and torches x4; no later coal-consumption craft event exists.
- The step-10200 hotbar shows coal x2 and torches x3; no coal consumption event occurred after the torch craft.
- Step-10800 hotbar visibly shows coal x2 and torches x13.
- Step-6000 frame and complete event stream contain no coal/torch pickup or craft in this trajectory.
- Step-6600 hotbar and events through 6600 show no fuel or torch acquisition.
- Step-6000 hotbar and event stream show planks x3 and no coal/torch pickup or craft in this trajectory.
- Current-reset events and step_6000.png show no wood, planks, coal, or torch; hotbar slot 7 contains iron ore x3 and slot 8 is empty.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
