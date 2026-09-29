# location_surface_furnace_4688

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 4779
- updated_step: 5400
- depends_on: goal_furnace

## Statement

Refuted as a duplicate-trajectory location; the current furnace is underground near (-2993.5,55.5,-5563.5), not at (-2988,65,-5547).

## Evidence

- At step 4688 raw placement caused [INV] furnace -1 while the player was at (-2988.5,65,-5547.3); the step-4779 frame visibly shows a furnace-like gray block directly to the right.
- INV furnace -1 at 4688 and use_item furnace at 4691 verify placement; frame 4779 shows its side at arm's reach.
- Last-per-step map rows, use_item furnace at 4630, and successful GUI opening from (-2993.3,54,-5564.7) prove the current site.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
