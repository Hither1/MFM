# location_fresh_diamond_shaft_8229

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 8229
- updated_step: 9000
- depends_on: goal_iron_pickaxe, goal_mine_diamond_ore

## Statement

The this-run shaft at x=-3000.70, z=-5565.36 is traversal-verified from surface y65 to diamond level y11; a six-block open fall to y18 caused 3 damage, but the column then safely reached y11 at step 8917.

## Evidence

- Step 8229 is stationary at (-3000.69,65,-5565.13) after mine_block grass_block; the frame shows the placed furnace behind/below the foreground and an open dirt-edged column with stone ahead, while dig_down explicitly diagnosed an off-center shaft.
- After the step-8237 edge adjustment, final visited.csv rows hold x/z fixed while y falls 65 to 52; events verify ten consecutive stone breaks at 8265-8391 and frame 8400 shows active downward mining.
- Live step 8589 STATE is (-3000.70,38.00,-5565.36); the preceding dig_down broke 24 blocks, descended 27 levels in 352 mining ticks, and recorded no damage or lava stop.
- Final visited.csv rows show fixed x/z descent to y24 followed by a fall to y18 at steps 8793-8805; STATE at 8810 gives y18, health 16, and frame 8810 shows solid stone under the crosshair.
- Final-trajectory visited rows keep x/z fixed through y11; dig_down notes report 24 blocks/27 levels to y38, then the damage interruption at y18, then 7 blocks/7 levels with target depth reached at step 8917.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
