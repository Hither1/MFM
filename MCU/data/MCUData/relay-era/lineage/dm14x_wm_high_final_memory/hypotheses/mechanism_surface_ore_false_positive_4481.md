# mechanism_surface_ore_false_positive_4481

- kind: mechanism
- status: confirmed
- confidence: 0.99
- created_step: 4481
- updated_step: 4481
- depends_on: goal_mine_iron_ore

## Statement

The ore watcher can false-positive on exposed surface dirt/grass texture; the step-4481 flag at screen coordinate (65,154) is not iron and should be ignored while centering into the shaft.

## Evidence

- A 4x crop of episodes/ep_0000/frames/step_4481_ore.png around the flagged coordinate visibly shows only green grass and brown dirt pixels, with no grey stone or tan iron-ore texture.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
