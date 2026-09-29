# resource_dropped_crafting_inputs_4034

- kind: resource
- status: active
- confidence: 0.50
- created_step: 4043
- updated_step: 4200
- depends_on: goal_furnace, resource_current_lighting_kit

## Statement

Cobblestone x11 and sticks x2 were dropped near the surface table at step 4034, but a 120-tick sweep recovered nothing; their exact item-entity position is unknown and recovery should be retired unless they become visible.

## Evidence

- The step-4034 runner note explicitly reports closing with cobblestonex11 and stickx2 outside inventory; the player has not moved through step 4043.
- The forced-close note at 4034 names both stacks; collect_drops through step 4169 moved 1.21 blocks and explicitly picked up nothing.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
