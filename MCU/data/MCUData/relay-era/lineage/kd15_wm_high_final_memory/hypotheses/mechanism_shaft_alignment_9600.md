# mechanism_shaft_alignment_9600

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 9600
- updated_step: 4200
- depends_on: location_live_shaft_3600

## Statement

The live shaft alignment near x=-2999.5 to -2999.7,z=-5576.7 is confirmed: after an offset dig broke walls with zero descent, recentering west enabled reliable y67-to-y49 descent.

## Evidence

- Position stayed y64 through block breaks at 9481/9502 and multiple dig_down calls, then moved y64 to y61 during the z correction at steps 9587-9596.
- At step 3727 the west strafe moved x from -2999.06 to -2999.49; the following dig_down reached y60 by step 3825, broke four blocks, and recovered cobblestone x3 plus dirt x4 after prior lip-aligned calls failed to descend.
- Current actions report y67-to-y60 in 98 ticks and y60-to-y49 in 204 ticks from the corrected alignment; visited.csv independently verifies the full descent.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
