# location_y56_west_strip_4800

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 4800
- updated_step: 4800
- depends_on: location_live_return_shaft_3449

## Statement

Refuted for the live checkpoint: this node describes a future-trajectory y56 branch after step 4810, while the authoritative current player is at (-2993.30,50,-5564.30) in the iron-pocket pit.

## Evidence

- maps/visited.csv fixes the pose through step 4800; events show stone breaks at 4759/4777/4795; the current frame visibly shows the short west tunnel.
- Step-5126 STATE gives x=-2999.30 at unchanged z and yaw -90 (east); strip_mine reports 5.1 blocks advanced, while events 4834-5123 contain 13 stone breaks and no iron ore.
- Strip reports advanced 5.1 then 4.2 blocks; maps/visited.csv step 5400 gives the endpoint; events 4834-5397 are stone only and torch use fired at 5356.
- Last-per-step visited row 4800 and live logs fix the y50 pose; the prior statement cites steps 5126/5400 beyond the current horizon.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
