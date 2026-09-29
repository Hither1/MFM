# mechanism_vertical_mine_ahead_rate_10200

- kind: mechanism
- status: confirmed
- confidence: 0.99
- created_step: 10200
- updated_step: 11338
- depends_on: location_diamond_depth_shaft_10138

## Statement

With the iron pick centered at pitch about 88, fixed mine_ahead descends ordinary stone at one level every 14 ticks; it succeeds when repeated dig_down calls are truncated with no y change.

## Evidence

- Four consecutive 100-tick segments descended y55→48→41→35→27.9 while breaking 27 blocks.
- Stone breaks occur at steps 11142, 11156, then every 14 ticks through 11338 while map y falls 60 to 45. Earlier fixed attack fell y65 to60 in 80 ticks.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
