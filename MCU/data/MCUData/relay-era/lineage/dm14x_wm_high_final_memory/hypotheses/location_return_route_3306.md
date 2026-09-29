# location_return_route_3306

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 3387
- updated_step: 3600
- depends_on: location_current_crafting_table, location_return_wall_2537

## Statement

Refuted for the live run: no table-return route was confirmed at step 3387; the player remained at y55 and the ascent is still unverified.

## Evidence

- Steps 3306-3387 verify movement from the dead end to (-3007.6,62,-5559.5), a two-block dirt-pillar rise to y64, traversal along the known tunnel, and arrival at (-3004.3,64,-5566.3). The step-3387 frame shows daylight through the dirt shaft overhead.
- maps/visited.csv fixes step 3387 at the y55 worksite, contradicting the inherited statement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
