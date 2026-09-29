# location_uncollected_iron_drops_6600

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 6600
- updated_step: 7200
- depends_on: location_live_iron_floor_6282, resource_current_iron_ore, goal_mine_iron_ore

## Statement

Refuted as cross-trajectory contamination: the alleged iron breaks at 6427/6542 and unrecovered drops do not occur in this current prefix.

## Evidence

- Breaks at 6427 and 6542 have no pickup events; the 6492 sweep moved only 0.4 block and recovered nothing, while step_6600 shows the opened floor pocket.
- At steps 6492, 6657, 6725, and 6791 collect_drops changed no inventory; forward attempts at steps 6665 and 6731 moved zero blocks. Live inventory at step 6815 still contains only iron_ore x1.
- Current events at 6427/6542 contain no iron-ore breaks; all three required ingots were already produced from verified ore by step 6107.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
