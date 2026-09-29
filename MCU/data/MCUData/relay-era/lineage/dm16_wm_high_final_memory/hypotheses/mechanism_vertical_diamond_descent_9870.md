# mechanism_vertical_diamond_descent_9870

- kind: mechanism
- status: refuted
- confidence: 0.00
- created_step: 9870
- updated_step: 10800
- depends_on: goal_iron_pickaxe, goal_mine_diamond_ore

## Statement

Refuted for this checkpoint: no iron-pickaxe diamond descent occurred; the live player remains in the y55 iron-search tunnel.

## Evidence

- Iron-pick stone breaks have taken about 10-15 ticks each; descending 19 blocks to y40 should fit within this turn's 390-tick action budget, while the staircase method is now proven too slow.
- At step 10138, dig_down had broken 19 blocks and descended exactly 19 levels in 265 ticks; position was (-3040.30,40.00,-5561.70), health 20/20, and the iron pick retained 205 uses.
- Action 645: dig_down(n=390,until_y=40) broke 19 blocks and reached y40 with full health. Actions 646-647: n=400 each executed only one tick with procedure-truncated notes.
- visited.csv proves the fixed shaft at (-3040.30,-5561.70), y59->37.77; step 10138 note reports 19 blocks/19 levels/265 ticks with full health; events verify two further dirt breaks at 10161/10182.
- Ground-truth states/maps show continuous descent at x=-3040.30,z=-5561.70 to y11 by step 10589; notes report 19 levels/265 ticks, 24.8/390, and 4/57 with no health-loss interruption.
- Current STATE is y55, progress is 6/24, and events contain no iron pickaxe; the y11 map rows belong to a duplicate future trajectory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
