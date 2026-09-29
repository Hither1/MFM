# mechanism_sticks_as_furnace_fuel_10834

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 10834
- updated_step: 11000
- depends_on: resource_current_lighting_kit, resource_current_iron_ore, goal_iron_ingot

## Statement

Two sticks are sufficient furnace fuel for one iron-ore smelt in this live run: exactly two were deposited and the furnace is actively burning, while two sticks remain for the iron-pick recipe.

## Evidence

- Live state at step 10834 has sticks x4 and iron ore x1; vanilla 1.16 stick burn time is 100 ticks each versus 200 ticks needed per smelt. This turn routes to the furnace to test loading two sticks.
- Steps 10976-10991 show INV stick -4, two right-clicks over the active furnace fuel cell, then INV stick +2; frame 11000 shows ore, stick fuel, and flame.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
