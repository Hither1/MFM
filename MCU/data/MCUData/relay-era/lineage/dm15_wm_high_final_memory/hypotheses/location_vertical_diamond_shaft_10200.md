# location_vertical_diamond_shaft_10200

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 10200
- updated_step: 10200
- depends_on: mechanism_vertical_diamond_descent_9870, goal_iron_pickaxe

## Statement

Retired as future-trajectory contamination: the actual step-10200 player is at y55 in a level iron-search branch, not in a diamond shaft.

## Evidence

- maps/visited.csv records the same x/z continuously from y59 through y37.77, ending at step 10200.
- Action 648 used dig_down for 390 ticks, broke 24 blocks, descended 24.8 levels from y40 to y15.23, retained full health, and maps/visited.csv shows fixed x/z throughout.
- maps/visited.csv records the fixed x/z route continuously to y11; step 10589 STATE confirms the endpoint.
- Claim cites steps after 10200 and contradicts current shallow coverage.
- Ground-truth visited.csv row 10200 is (-3019.70,55.00,-5580.70), and iron pickaxe is unmet.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
