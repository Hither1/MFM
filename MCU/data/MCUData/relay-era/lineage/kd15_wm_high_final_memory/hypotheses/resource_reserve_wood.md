# resource_reserve_wood

- kind: resource
- status: stale
- confidence: 0.95
- created_step: 2400
- updated_step: 6000
- depends_on: goal_stone_pickaxe, goal_iron_pickaxe, goal_furnace, goal_iron_ingot

## Statement

The step-5400 wood-reserve snapshot is historical and superseded: three sticks, coal, and torches now exist, while no logs or planks are held.

## Evidence

- Step-2400 hotbar visibly contains sticks x2 and no planks; the forced close at step 2099 reported planks x3 dropped, and no later plank pickup/craft event exists. A proven spruce site is nearby around (-3002.7,64,-5556.3).
- craft_item stick +4 fired at step 2602 after two sticks were already held, and step_3000.png shows sticks x6 with no planks. Proven spruce is at (-3002.7,64,-5556.3).
- [INV] stick +4 at step 4158 after two sticks were placed; step-4200 hotbar shows 4 sticks. No later pickup/craft event supplies wood or coal.
- Step-4800 hotbar shows sticks x4 and no wood/coal/ore; coal is still needed for light and preferably fuel.
- Step-5400 hotbar shows sticks x4 and no wood/coal/ore; events through 5400 contain no later wood, coal, ore, or ingot pickup.
- Torch crafting at 5746 consumed one of four sticks; step-6000 hotbar shows sticks x3, coal x2, torches x3 and no wood.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
