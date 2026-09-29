# location_furnace_surface_3582

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 3600
- updated_step: 3600
- depends_on: goal_furnace

## Statement

No furnace exists in the current reset at step 3600; the purported step-3582 placement is from another trajectory and is refuted by the current event stream.

## Evidence

- [INV] furnace -1 at 3579 and use_item furnace at 3582 verify placement; subsequent movement reached only (-3003.50,67,-5565.24).
- Current events contain no craft_item/use_item furnace, the milestone remains unmet, and step_3600.png has no furnace item.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
