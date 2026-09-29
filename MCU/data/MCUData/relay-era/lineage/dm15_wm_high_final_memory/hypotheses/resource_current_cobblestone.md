# resource_current_cobblestone

- kind: resource
- status: refuted
- confidence: 0.00
- created_step: 2400
- updated_step: 10400
- depends_on: goal_wooden_pickaxe, goal_mine_cobblestone, location_live_return_shaft_3449, resource_wooden_pickaxe_secure, location_live_shaft_1200, location_surface_recovery_7749, location_live_descent_2308, location_live_dirt_face_2400

## Statement

The former claim that the live player owns cobblestone x35 is false after the step-10194 deliberate cursor drop; frame 10400 shows its old hotbar slot empty and no later cobblestone pickup occurred.

## Evidence

- Starting from x13 at step 3822, pickup events at 3826, 3885, 3934, 3956, 3982, 4004, 4030, 4052, 4078, 4119, 4138, 4159, and 4179 plus five later cobble placements account to x22; frame 4200 visibly shows 22.
- Frame 4800 visibly shows x35. Starting from verified x22 at 4200, current INV/event deltas for mining, pickups, and placements reconcile to x35.
- Starting from frame-4800 x35, current events add 18 cobblestone pickups and one placement; frame 5400 visibly confirms x52.
- INV returned cobblestone +40 to hotbar slot 4 at step 5989; the 3x3 ring then cleared and craft_item furnace fired at 5997.
- Frame 8600 visibly reports cobblestone x57; current events record the latest overhead breaks and pickups through 8457.
- Authoritative step-8863 STATE reports cobblestone x40 and dirt x5; placement events through 8822 reconcile the reduction from x57, and the gravel placement at 8848 is separately verified.
- Frame 9200 visibly shows cobblestone x35; placement events through 8961 account for the reduction from the prior stack.
- Logs record INV cobblestone -35 at step 10191 and the force-close drop note at 10194; the 72-tick sweep through 10342 gained nothing, events contain no later cobblestone pickup, and frame 10400 shows slot 5 empty.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
