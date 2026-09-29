# location_fresh_direct_descent_2530

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 2530
- updated_step: 3000
- depends_on: resource_wooden_pickaxe_secure, resource_free_cobblestone_slot_2500, mechanism_pitch80_mine_ahead_4800

## Statement

The this-run one-block shaft at x=-2995.70,z=-5565.70 is confirmed open from y65 to y56; pitch-80 mine_ahead broke one dirt and eight stone while lowering the player nine levels.

## Evidence

- At step 2530 STATE is stationary at the fresh coordinate with pitch 88 and the wooden pick selected; events through 2530 contain no break from the clipped dig_down entry, so actual descent remains untested.
- At steps 2530-2531 two 40-tick dig_down attempts at pitch 88 produced no mine_block event or movement, and the governor now rejects that repetition. The confirmed pitch-80 mine_ahead mechanism previously descended through near-underfoot blocks.
- STATE moved from y65 to y56 during steps 2532-2872; events verify the nine breaks and eight cobblestone pickups, while the attached frame visibly shows tan-speckled iron ore around the downward crosshair.
- Final map rows move y65 to y56 at fixed x/z during steps 2532-2872; events verify one dirt and eight stone breaks with eight cobblestone pickups.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
