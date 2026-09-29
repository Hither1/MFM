# location_live_east_branch_3600

- kind: location
- status: active
- confidence: 1.00
- created_step: 3600
- updated_step: 5400
- depends_on: location_live_coal_shaft_2814, resource_stone_pickaxe_secure

## Statement

The current y55 L-route is traversable from shaft foot (-3008.3,-5559.7) east to (-2993.3,-5559.7), then north to the furnace worksite; the y50 pit has now been pillared back to y54.

## Evidence

- Events record furnace break/pickup at 3565/3575 and stone break at 3585; visited.csv remains x=-3008.30,z=-5559.70 through 3600.
- Authoritative step-3917 state is pos=(-3002.3,55,-5559.7), and the preceding mine_forward reports 15 blocks broken with 6.0 blocks advanced from (-3008.3,55,-5559.7).
- maps/visited.csv fixes step 4200 at (-2996.30,55,-5559.70); events 3941-4181 record twelve stone breaks and the recent segment advanced six blocks.
- Last-per-step visited rows and authoritative states at 4314/4624 prove the L-route; rows 4669-4800 prove the subsequent drop to y50.
- Visited rows verify the route; dirt use at 4840-4884 raised the player from y50 to y54 at the worksite.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
