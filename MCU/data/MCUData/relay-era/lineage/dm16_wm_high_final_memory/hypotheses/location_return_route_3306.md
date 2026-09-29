# location_return_route_3306

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 3387
- updated_step: 3600
- depends_on: location_current_crafting_table, location_return_wall_2537

## Statement

Refuted as alternate-trajectory contamination: the claimed route through x about -2995 does not describe the live return, which was already at the spawn worksite near x -3007 by step 3300.

## Evidence

- Steps 3306-3387 verify movement from the dead end to (-3007.6,62,-5559.5), a two-block dirt-pillar rise to y64, traversal along the known tunnel, and arrival at (-3004.3,64,-5566.3). The step-3387 frame shows daylight through the dirt shaft overhead.
- maps/visited.csv fixes step 3387 at the y55 worksite, contradicting the inherited statement.
- Final visited rows 3249-3330 trace the ascent and surface route; GUI open=True at 3330 and craft_item stone_pickaxe at 3390 prove table access.
- Last-per-step map row 3300 is (-3006.87,69,-5564.70); the node's cited duplicate row belongs to another stored trajectory.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
