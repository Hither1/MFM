# goal_mine_diamond_ore

- kind: goal
- status: active
- confidence: 0.15
- created_step: 600
- updated_step: 11995
- depends_on: goal_iron_pickaxe, location_live_shaft_3600

## Statement

The live run ended with the mine_diamond_ore milestone still unmet after all tested west-pocket center, side, upper, and lower-floor rays exposed only stone or gravel; the final five ticks continue the already-centered lower-west ray as the only remaining scoring chance.

## Evidence

- events/events.jsonl records the mine_diamond_ore milestone and mine_block diamond_ore at step 10362; the authoritative state reports 10/24 verified.
- Current events contain no mine_block diamond_ore; the registered vein is a permanent seed fact, not live excavation.
- Current events through step 10792 contain no diamond-ore break. Final-reset maps place the player at (-2991.70,9,-5572.30), while the permanent approach is near x=-2999.3.
- Current STATE is (-2993.7,9.0,-5572.3), facing west with an iron pickaxe at 195/250 uses; events through step 10906 show only stone breaks and cobblestone pickups.
- Current pose is (-2999.46,9,-5572.30), within about 1.1 blocks of the seed-stable face; current events still contain no diamond-ore break.
- Current events contain no diamond ore or milestone. Final map pose is (-2999.75,9,-5572.30); the target ray produced mine_block stone at 11365 and gravel at 11389.
- Live events from steps 11480 through 11677 record only stone/gravel breaks. The four offset rays targeted y=9.5 and y=10.5, leaving the floor block layer at y=8.5 untested.
- At steps 11760-11973, the three y=8.5 floor probes and the y=7.5 lower-west probe produced only mine_block gravel events; no current mine_block diamond_ore event exists at step 11995.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
