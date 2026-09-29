# resource_cobblestone_descent_1639

- kind: resource
- status: refuted
- confidence: 1.00
- created_step: 1639
- updated_step: 2400
- depends_on: goal_wooden_pickaxe, goal_mine_cobblestone

## Statement

The old claim about three placed planks and a y62 descent at (-2999.30,-5576.70) belongs to another trajectory and must not guide current inventory or routing.

## Evidence

- At step 1639 the authoritative state has spruce_planks x2, stick x2, and wooden_pickaxe x1 with zero free slots; pitch 88 is already downward, and the prior oblique back-use consumed one plank at step 1625.
- Events verify three spruce_plank uses at 1625/1647/1659 and four dirt pickups through 1788. Current map pose is (-2999.30,62,-5576.70), and step_1800.png visibly shows the wooden pick cracking stone with dirt x4 and sticks x2 in the hotbar.
- Current events have no use_item spruce_planks and current-reset maps put step 1800 at (-3001.48,51,-5565.31).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
