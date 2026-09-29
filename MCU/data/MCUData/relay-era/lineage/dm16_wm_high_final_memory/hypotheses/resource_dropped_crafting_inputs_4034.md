# resource_dropped_crafting_inputs_4034

- kind: resource
- status: stale
- confidence: 1.00
- created_step: 4043
- updated_step: 8400
- depends_on: goal_furnace, resource_current_lighting_kit

## Statement

The uncertain surface crafting-input cache is retired; its recovery was never verified and no remaining recipe contributes to diamond pickup.

## Evidence

- The step-4034 runner note explicitly reports closing with cobblestonex11 and stickx2 outside inventory; the player has not moved through step 4043.
- The forced-close note at 4034 names both stacks; collect_drops through step 4169 moved 1.21 blocks and explicitly picked up nothing.
- Furnace and iron-pick milestones are verified, while the live player is at y11 with only diamond unmet.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
