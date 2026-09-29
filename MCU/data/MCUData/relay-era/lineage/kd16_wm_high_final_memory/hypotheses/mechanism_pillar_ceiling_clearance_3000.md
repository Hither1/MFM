# mechanism_pillar_ceiling_clearance_3000

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 3000
- updated_step: 3000
- depends_on: location_current_pillar_3000, mechanism_dirt_pillar_return_2325

## Statement

At a fixed pillar column, failed jump-use with no item event means headroom is blocked; mining straight up through stone/dirt/grass and then resuming look-down jump-use restores roughly one settled level per solid block.

## Evidence

- Repeated jump-use attempts at y61 produced neither item use nor y gain, direct go_to was blocked, and the step-3000 frame is aimed at the overhead face with the wooden pick selected.
- At steps 3010 and 3034 the overhead dirt and grass broke; subsequent cobblestone jump-placements at steps 3062, 3147, and 3232 advanced the settled pillar from y61 toward the surface without another no-rise failure.
- The step-2856 jump-use gained nothing at y61; mine_ahead through four overhead blocks completed at 2964, then cobblestone uses at 2981 and 2993 raised the player to y63.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
