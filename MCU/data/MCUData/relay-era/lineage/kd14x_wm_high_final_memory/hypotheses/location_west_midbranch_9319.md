# location_west_midbranch_9319

- kind: location
- status: refuted
- confidence: 0.95
- created_step: 9319
- updated_step: 9455
- depends_on: location_south_level_tunnel_7200, goal_mine_iron_ore

## Statement

The attempted westbound branch from z=-5551.9 is not a dry productive route: water displaced the player about four blocks north while four ordinary blocks broke, and the mining macro stopped for no forward progress.

## Evidence

- Visited coordinates show only the north-south corridor at this z; the west face here has not been tested, unlike west at z=-5557.2.
- Steps 9337-9455: yaw 90 throughout, but position changed mainly from z=-5551.88 to -5556.16 while x changed only -0.39; four diorite/stone blocks broke and strip_mine reported only 0.6 forward advance before stalling.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
